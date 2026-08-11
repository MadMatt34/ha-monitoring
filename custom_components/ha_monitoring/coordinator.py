"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_STARTUP_DELAY,
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_OFFLINE,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
    CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
    CONF_EXCLUDED_UNAVAILABLE_GLOBS,
    CONF_EXCLUDED_UPDATES,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    CONF_SYSTEM_INFO_SCAN_INTERVAL,
    CONF_TRACES_SCAN_INTERVAL,
    DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    DEFAULT_LAST_SEEN_SUFFIX,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
    LOCALIZED_LAST_SEEN_SUFFIX,
)
from .helpers.backup import async_get_backup_info
from .helpers.system import (
    async_get_addons,
    async_get_failed_integrations,
    async_get_pending_repairs,
    scan_all_states,
)
from .helpers.system_info import async_get_system_stats
from .helpers.trace import get_trace_errors

_LOGGER = logging.getLogger(__name__)


class HAMonitoringCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator principal gérant les collectes et la temporisation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le coordinateur."""
        self.entry = entry

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        if "ha_start_time" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["ha_start_time"] = dt_util.utcnow()

        self._ha_start_time = hass.data[DOMAIN]["ha_start_time"]
        self._cached_backup_info: dict[str, Any] | None = None
        self._last_backup_event: Any | None = None
        self._last_backup_event_time: Any = None
        self._backup_event_unsub: Callable[[], None] | None = None
        self._unsub_ha_started: Callable[[], None] | None = None
        self._startup_timer_unsub: Callable[[], None] | None = None

        self._last_trace_check_time: Any = None
        self._cached_automations: list[dict[str, Any]] = []
        self._cached_scripts: list[dict[str, Any]] = []

        # Cache et temporisation pour System Info
        self._last_system_stats_check_time: Any = None
        self._cached_system_stats: dict[str, Any] | None = None

        # --- Initialisation de la temporisation de démarrage ---
        self._setup_startup_delay(hass, entry)

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

        backup_data = hass.data.get("backup")
        backup_manager = getattr(backup_data, "manager", backup_data)
        if backup_manager and hasattr(backup_manager, "async_subscribe_events"):
            self._backup_event_unsub = backup_manager.async_subscribe_events(
                self._async_backup_event
            )

    def _setup_startup_delay(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Gère la temporisation post-démarrage (EVENT_HOMEASSISTANT_STARTED + CONF_STARTUP_DELAY)."""
        startup_delay = float(entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
        now = dt_util.utcnow()
        elapsed = (now - self._ha_start_time).total_seconds()

        # Cas 1 : HA tourne déjà et le délai post-boot est déjà dépassé (ex: rechargement à chaud)
        if hass.state == CoreState.running and elapsed >= startup_delay:
            self._is_ready = True
            return

        self._is_ready = False

        @callback
        def _start_delay_timer(delay: float) -> None:
            if delay <= 0:
                self._is_ready = True
                _LOGGER.info(
                    "[HA Monitoring] Démarrage terminé. Lancement immédiat du premier scan."
                )
                self.entry.async_create_background_task(
                    self.hass, self.async_refresh(), "ha_monitoring_startup_refresh"
                )
                return

            _LOGGER.info(
                "[HA Monitoring] Home Assistant est démarré. Attente de %ss (CONF_STARTUP_DELAY) avant premier scan...",
                delay,
            )

            @callback
            def _on_timer_complete(_: Any) -> None:
                self._startup_timer_unsub = None
                self._is_ready = True
                _LOGGER.info(
                    "[HA Monitoring] Fin du temporisateur de démarrage. Lancement du premier scan."
                )
                self.entry.async_create_background_task(
                    self.hass, self.async_refresh(), "ha_monitoring_startup_refresh"
                )

            self._startup_timer_unsub = async_call_later(self.hass, delay, _on_timer_complete)

        # Cas 2 : HA tourne déjà mais le délai post-boot n'est pas encore écoulé
        if hass.state == CoreState.running:
            remaining = max(0.1, startup_delay - elapsed)
            _start_delay_timer(remaining)
        # Cas 3 : HA est en cours de boot -> On attend la fin du boot puis on arme le temporisateur
        else:

            @callback
            def _on_ha_started(_: Event) -> None:
                self._unsub_ha_started = None
                delay = float(self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
                _start_delay_timer(delay)

            self._unsub_ha_started = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _on_ha_started
            )

    @callback
    def _async_backup_event(self, event: Any) -> None:
        """Observe le résultat final des sauvegardes gérées par HA."""
        state = getattr(event, "state", None)
        state_value = getattr(state, "value", state)
        if state_value not in ("completed", "failed"):
            return
        self._last_backup_event = event
        self._last_backup_event_time = dt_util.now()
        self._cached_backup_info = None
        self.entry.async_create_background_task(
            self.hass,
            self.async_refresh(),
            "ha_monitoring_backup_refresh",
        )

    def _get_last_seen_suffixes(self) -> tuple[str, ...]:
        """Retourne la liste des suffixes/attributs 'last_seen' applicables."""
        suffixes = set(DEFAULT_LAST_SEEN_SUFFIX)
        lang = self.hass.config.language
        localized_suffix = LOCALIZED_LAST_SEEN_SUFFIX.get(lang)
        if localized_suffix:
            suffixes.add(localized_suffix.lower())

        return tuple(suffixes)

    async def async_on_backup_completed(self) -> None:
        """Appelé lorsqu'une sauvegarde vient de se terminer."""
        _LOGGER.debug(
            "[HA Monitoring] Invalidation du cache de sauvegarde suite au signal post-backup."
        )
        self._cached_backup_info = None
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        """Détruit proprement les écouteurs et temporisateurs lors de la fermeture."""
        if self._unsub_ha_started:
            self._unsub_ha_started()
            self._unsub_ha_started = None

        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        if self._backup_event_unsub:
            self._backup_event_unsub()
            self._backup_event_unsub = None

        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force un rafraîchissement immédiat de toutes les données sans temporisation."""
        if self._unsub_ha_started:
            self._unsub_ha_started()
            self._unsub_ha_started = None

        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._is_ready = True
        self._last_trace_check_time = None
        self._cached_backup_info = None
        self._last_system_stats_check_time = None
        self._cached_system_stats = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Récupère l'ensemble des métriques d'état du système."""
        now = dt_util.utcnow()

        fetched_info = None
        if self._cached_backup_info is None:
            _LOGGER.debug("[HA Monitoring] Interrogation des infos de sauvegarde...")
            fetched_info = await async_get_backup_info(
                self.hass,
                backup_event=self._last_backup_event,
                backup_event_time=self._last_backup_event_time,
                previous_info=self._cached_backup_info,
            )
            if self._is_ready or fetched_info.get("date_last_run") is not None:
                self._cached_backup_info = fetched_info
            self._last_backup_event = None
            self._last_backup_event_time = None

        current_backup_info = (
            self._cached_backup_info
            or fetched_info
            or self._empty_results(False)["monitoring_backup"]
        )

        # Tant que la temporisation post-boot (CONF_STARTUP_DELAY) n'est pas écoulée : zéro scan
        if not self._is_ready:
            results = self._empty_results(in_startup_delay=True)
            results["monitoring_backup"] = current_backup_info
            return results

        options = self.entry.options
        offline_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)

        excluded_unavailable_entities = options.get(CONF_EXCLUDED_UNAVAILABLE_ENTITIES, [])
        excluded_unavailable_domains = options.get(
            CONF_EXCLUDED_UNAVAILABLE_DOMAINS, DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS
        )
        excluded_unavailable_globs = options.get(CONF_EXCLUDED_UNAVAILABLE_GLOBS, [])

        last_seen_suffixes = self._get_last_seen_suffixes()

        # Balayage complet des états
        updates, unavailable, offline = scan_all_states(
            self.hass,
            excluded_updates=options.get(CONF_EXCLUDED_UPDATES, []),
            excluded_unavailable_entities=excluded_unavailable_entities,
            excluded_unavailable_domains=excluded_unavailable_domains,
            excluded_unavailable_globs=excluded_unavailable_globs,
            excluded_offline=options.get(CONF_EXCLUDED_OFFLINE, []),
            timeout_hours=offline_timeout,
            last_seen_suffixes=last_seen_suffixes,
        )

        traces_scan_interval_min = options.get(
            CONF_TRACES_SCAN_INTERVAL, DEFAULT_TRACES_SCAN_INTERVAL
        )
        traces_scan_interval_sec = float(traces_scan_interval_min) * 60

        if (
            self._last_trace_check_time is None
            or (now - self._last_trace_check_time).total_seconds() >= traces_scan_interval_sec
        ):
            self._cached_automations = get_trace_errors(
                self.hass, "automation", options.get(CONF_EXCLUDED_AUTOMATIONS, [])
            )
            self._cached_scripts = get_trace_errors(
                self.hass, "script", options.get(CONF_EXCLUDED_SCRIPTS, [])
            )
            self._last_trace_check_time = now

        # Collecte de System Info
        system_info_scan_interval_hours = options.get(
            CONF_SYSTEM_INFO_SCAN_INTERVAL, DEFAULT_SYSTEM_INFO_SCAN_INTERVAL
        )
        system_info_scan_interval_sec = float(system_info_scan_interval_hours) * 3600

        if (
            self._last_system_stats_check_time is None
            or self._cached_system_stats is None
            or (now - self._last_system_stats_check_time).total_seconds()
            >= system_info_scan_interval_sec
        ):
            self._cached_system_stats = await async_get_system_stats(self.hass, self._ha_start_time)
            self._last_system_stats_check_time = now

        addons = await async_get_addons(self.hass, options.get(CONF_EXCLUDED_ADDONS, []))
        integrations = await async_get_failed_integrations(
            self.hass, options.get(CONF_EXCLUDED_INTEGRATIONS, [])
        )
        repairs = await async_get_pending_repairs(self.hass, options.get(CONF_EXCLUDED_REPAIRS, []))

        return {
            ATTR_STARTUP_DELAY: False,
            "system_stats": self._cached_system_stats,
            "monitoring_addons": {"items": addons, "total": len(addons)},
            "monitoring_integrations": {
                "items": integrations,
                "total": len(integrations),
            },
            "monitoring_automations": {
                "items": self._cached_automations,
                "total": len(self._cached_automations),
            },
            "monitoring_scripts": {
                "items": self._cached_scripts,
                "total": len(self._cached_scripts),
            },
            "monitoring_updates": {"items": updates, "total": len(updates)},
            "monitoring_repairs": {"items": repairs, "total": len(repairs)},
            "monitoring_unavailable": {
                "items": unavailable,
                "total": len(unavailable),
            },
            "monitoring_offline": {
                "items": offline,
                "total": len(offline),
                "timeout": offline_timeout,
            },
            "monitoring_backup": self._cached_backup_info,
        }

    def _empty_results(self, in_startup_delay: bool) -> dict[str, Any]:
        """Génère la structure par défaut pendant le délai de démarrage."""
        timeout = self.entry.options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)
        return {
            ATTR_STARTUP_DELAY: in_startup_delay,
            "system_stats": {},
            "monitoring_addons": {"items": [], "total": 0},
            "monitoring_integrations": {"items": [], "total": 0},
            "monitoring_automations": {"items": [], "total": 0},
            "monitoring_scripts": {"items": [], "total": 0},
            "monitoring_updates": {"items": [], "total": 0},
            "monitoring_repairs": {"items": [], "total": 0},
            "monitoring_unavailable": {"items": [], "total": 0},
            "monitoring_offline": {"items": [], "total": 0, "timeout": timeout},
            "monitoring_backup": {
                "is_ok": True,
                "date_last_run": None,
                "date_last_success": None,
                "date_next_schedule": None,
                "size": None,
                "failure": None,
            },
        }
