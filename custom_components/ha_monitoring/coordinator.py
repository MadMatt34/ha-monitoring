"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.translation import async_get_translations
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
    CONF_EXCLUDED_UPDATES,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    CONF_TRACES_SCAN_INTERVAL,
    DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    DEFAULT_LAST_SEEN_ATTRS,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
)
from .helpers.backup import async_get_backup_info
from .helpers.system import (
    async_get_addons,
    async_get_failed_integrations,
    async_get_pending_repairs,
    scan_all_states,
)
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
        self._startup_timer_unsub: Any = None
        self._bus_listeners_unsub: list[Any] = []

        self._last_trace_check_time: Any = None
        self._cached_automations: list[dict[str, Any]] = []
        self._cached_scripts: list[dict[str, Any]] = []

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

    def _setup_backup_listeners(self) -> None:
        """Écoute les événements du bus déclenchés lors des sauvegardes."""
        async def _async_on_backup_event(event: Event) -> None:
            _LOGGER.debug(
                "[HA Monitoring] Événement de sauvegarde détecté : %s",
                event.event_type,
            )
            try:
                if event.event_type == "backup_failed" or event.data.get("status") == "failed":
                    self._last_backup_failure_reason = (
                        event.data.get("reason")
                        or event.data.get("error")
                        or event.data.get("message")
                        or "Échec de sauvegarde signalé par événement"
                    )

                self._cached_backup_info = await async_get_backup_info(
                    self.hass, self._last_backup_failure_reason
                )
                self.async_update_listeners()
            except Exception as err:
                _LOGGER.error("[HA Monitoring] Erreur traitement événement backup : %s", err)

        for event_type in (
            "backup_completed",
            "backup_successful",
            "backup_failed",
            "hassio_backup_completed",
        ):
            unsub = self.hass.bus.async_listen(event_type, _async_on_backup_event)
            self._bus_listeners_unsub.append(unsub)

    async def async_shutdown(self) -> None:
        """Détruit proprement les écouteurs et temporisateurs lors de la fermeture."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        for unsub in self._bus_listeners_unsub:
            unsub()
        self._bus_listeners_unsub.clear()

        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force un rafraîchissement immédiat de toutes les données sans temporisation."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._skip_startup_delay = True
        self._last_trace_check_time = None
        self._cached_backup_info = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Récupère l'ensemble des métriques d'état du système."""
        startup_delay = float(self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._ha_start_time).total_seconds()

        in_startup_phase = (
            not self._skip_startup_delay
            and (self.hass.state != CoreState.running or elapsed_seconds < (startup_delay - 0.5))
        )

        # Mise à jour du cache de sauvegarde si nécessaire
        if self._cached_backup_info is None:
            self._cached_backup_info = await async_get_backup_info(
                self.hass, self._last_backup_failure_reason
            )

        # Traitement de la période d'initialisation
        if in_startup_phase:
            remaining = max(0.0, startup_delay - elapsed_seconds)

            if not self._startup_timer_unsub and remaining > 0:
                @callback
                def _force_refresh_after_delay(_: Any) -> None:
                    self._startup_timer_unsub = None
                    self.hass.async_create_task(self.async_refresh())

                self._startup_timer_unsub = async_call_later(
                    self.hass, remaining + 0.1, _force_refresh_after_delay
                )

            results = self._empty_results(in_startup_delay=True)
            results["monitoring_backup"] = self._cached_backup_info
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

        last_seen_suffixes = await self._async_get_last_seen_suffixes()

        # Balayage complet des états (système, hors-ligne, indisponibles, updates)
        updates, unavailable, offline = scan_all_states(
            self.hass,
            excluded_updates=options.get(CONF_EXCLUDED_UPDATES, []),
            excluded_unavailable_entities=excluded_unavailable_entities,
            excluded_unavailable_domains=excluded_unavailable_domains,
            excluded_offline=options.get(CONF_EXCLUDED_OFFLINE, []),
            timeout_hours=offline_timeout,
            last_seen_suffixes=last_seen_suffixes,
        )

        # Vérification périodique des traces d'erreurs (automations & scripts)
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

        # Collecte asynchrone des Add-ons, Intégrations et Réparations
        addons = await async_get_addons(self.hass, options.get(CONF_EXCLUDED_ADDONS, []))
        integrations = await async_get_failed_integrations(
            self.hass, options.get(CONF_EXCLUDED_INTEGRATIONS, [])
        )
        repairs = await async_get_pending_repairs(
            self.hass, options.get(CONF_EXCLUDED_REPAIRS, [])
        )

        return {
            "in_startup_delay": False,
            "monitoring_addons": {"items": addons, "total": len(addons)},
            "monitoring_integrations": {"items": integrations, "total": len(integrations)},
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
            "monitoring_unavailable": {"items": unavailable, "total": len(unavailable)},
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
                "date_next_schedule": "Démarrage...",
                "size": None,
                "failure": None,
            },
        }