"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
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
    TEMPO_BACKUP_EVENT,
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

_LOGGER = logging.getLogger("custom_components.ha_monitoring.coordinator")


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
        self._skip_startup_delay = False
        self._cached_backup_info: dict[str, Any] | None = None
        self._last_backup_failure_reason: str | None = None
        self._startup_timer_unsub: Callable[[], None] | None = None
        self._bus_listeners_unsub: list[Callable[[], None]] = []

        self._last_trace_check_time: Any = None
        self._cached_automations: list[dict[str, Any]] = []
        self._cached_scripts: list[dict[str, Any]] = []

        # Cache et temporisation pour System Info
        self._last_system_stats_check_time: Any = None
        self._cached_system_stats: dict[str, Any] | None = None

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

        self._setup_backup_listeners()

    def _get_last_seen_suffixes(self) -> tuple[str, ...]:
        """Retourne la liste des suffixes/attributs 'last_seen' applicables."""
        suffixes = set(DEFAULT_LAST_SEEN_SUFFIX)
        lang = self.hass.config.language
        localized_suffix = LOCALIZED_LAST_SEEN_SUFFIX.get(lang)
        if localized_suffix:
            suffixes.add(localized_suffix.lower())

        return tuple(suffixes)

    def _unsubscribe_backup_listeners(self) -> None:
        """Désabonne proprement tous les écouteurs du bus d'événements."""
        while self._bus_listeners_unsub:
            unsub = self._bus_listeners_unsub.pop()
            try:
                unsub()
            except Exception as err:
                _LOGGER.debug("[HA Monitoring] Erreur désabonnement : %s", err)

    def _setup_backup_listeners(self) -> None:
        """Écoute les événements du bus déclenchés lors de la fin d'une sauvegarde (succès ou échec)."""
        self._unsubscribe_backup_listeners()

        async def _async_on_backup_event(event: Event) -> None:
            _LOGGER.debug(
                "[HA Monitoring] Événement de sauvegarde détecté : %s (data: %s)",
                event.event_type,
                event.data,
            )
            try:
                data = event.data or {}
                event_type = event.event_type.lower()

                # Extraction robuste (dictionnaires plats ET imbriqués sous 'event')
                event_sub = data.get("event")
                sub_type = ""
                sub_state = ""
                if isinstance(event_sub, dict):
                    sub_type = str(event_sub.get("type", "")).lower()
                    sub_state = str(event_sub.get("state") or event_sub.get("status") or "").lower()
                elif isinstance(event_sub, str):
                    sub_type = event_sub.lower()

                status = str(
                    data.get("status") or data.get("state") or sub_state or sub_type
                ).lower()

                # On ignore uniquement si la sauvegarde vient de DÉBARRER ou est EN COURS
                if status in ("in_progress", "start", "started") or sub_type == "start":
                    return

                # Temp : Laisser quelques secondes à HA Core pour finaliser l'écriture et rafraîchir son registre
                import asyncio
                await asyncio.sleep(TEMPO_BACKUP_EVENT)

                # Détection d'un échec
                is_failed = (
                    "failed" in event_type
                    or status == "failed"
                    or "error" in data
                    or (isinstance(event_sub, dict) and "error" in event_sub)
                )

                if is_failed:
                    err_source = event_sub if isinstance(event_sub, dict) else data
                    self._last_backup_failure_reason = (
                        err_source.get("reason")
                        or err_source.get("error")
                        or err_source.get("message")
                        or "Échec de sauvegarde signalé par événement"
                    )
                else:
                    self._last_backup_failure_reason = None

                # Re-lecture des sauvegardes auprès de Home Assistant
                self._cached_backup_info = await async_get_backup_info(
                    self.hass, self._last_backup_failure_reason
                )

                # Notification immédiate de tous les capteurs
                self.async_update_listeners()

            except Exception as err:
                _LOGGER.error("[HA Monitoring] Erreur traitement événement backup : %s", err)

        backup_events = (
            "backup_event",  # Événement officiel nativement émis par HA Backup
            "backup_completed",
            "backup_successful",
            "backup_failed",
            "backup_end",
            "hassio_backup_completed",
            "hassio_backup_failed",
            "auto_backup_complete",
            "auto_backup_failed",
        )

        for event_type in backup_events:
            unsub = self.hass.bus.async_listen(event_type, _async_on_backup_event)
            self._bus_listeners_unsub.append(unsub)

    async def async_shutdown(self) -> None:
        """Détruit proprement les écouteurs et temporisateurs lors de la fermeture."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._unsubscribe_backup_listeners()
        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force un rafraîchissement immédiat de toutes les données sans temporisation."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._skip_startup_delay = True
        self._last_trace_check_time = None
        self._cached_backup_info = None
        self._last_system_stats_check_time = None
        self._cached_system_stats = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Récupère l'ensemble des métriques d'état du système."""
        startup_delay = float(self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._ha_start_time).total_seconds()

        in_startup_phase = not self._skip_startup_delay and (
            self.hass.state != CoreState.running or elapsed_seconds < (startup_delay - 0.5)
        )

        # Récupération uniquement si le cache est vide (premier démarrage)
        fetched_info = None
        if self._cached_backup_info is None:
            fetched_info = await async_get_backup_info(self.hass, self._last_backup_failure_reason)
            if not in_startup_phase or fetched_info.get("date_last_run") is not None:
                self._cached_backup_info = fetched_info

        current_backup_info = (
            self._cached_backup_info
            or fetched_info
            or self._empty_results(False)["monitoring_backup"]
        )

        if in_startup_phase:
            remaining = max(0.0, startup_delay - elapsed_seconds)

            if not self._startup_timer_unsub and remaining > 0:

                @callback
                def _force_refresh_after_delay(_: Any) -> None:
                    self._startup_timer_unsub = None
                    self.entry.async_create_background_task(
                        self.hass,
                        self.async_refresh(),
                        "ha_monitoring_startup_refresh",
                    )

                self._startup_timer_unsub = async_call_later(
                    self.hass, remaining + 0.1, _force_refresh_after_delay
                )

            results = self._empty_results(in_startup_delay=True)
            results["monitoring_backup"] = current_backup_info
            return results

        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

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

        # Collecte de System Info basée sur la durée configurée (en heures, convertie en secondes)
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
            "in_startup_delay": False,
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
            "in_startup_delay": in_startup_delay,
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
