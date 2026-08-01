"""DataUpdateCoordinator centralisé pour HA Monitoring."""
import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ADDONS_EN_ERREUR,
    ATTR_APPAREILS_HORS_LIGNE,
    ATTR_AUTOMATIONS_EN_ERREUR,
    ATTR_CORRECTIONS_EN_ATTENTE,
    ATTR_ENTITES_INDISPONIBLES,
    ATTR_INTEGRATIONS_EN_ERREUR,
    ATTR_MISES_A_JOUR_EN_ATTENTE,
    ATTR_SCRIPTS_EN_ERREUR,
    ATTR_TOTAL_EN_ATTENTE,
    ATTR_TOTAL_EN_ERREUR,
    ATTR_TOTAL_HORS_LIGNE,
    ATTR_TOTAL_INDISPONIBLES,
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_OFFLINE,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UNAVAILABLE,
    CONF_EXCLUDED_UPDATES,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DOMAIN,
    INTEGRATION_ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


class HAMonitoringCoordinator(DataUpdateCoordinator):
    """Coordinator principal gérant les collectes et la temporisation."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        self._boot_time = dt_util.utcnow()

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

    async def _async_update_data(self) -> dict:
        """Récupère les métriques système en respectant le délai de démarrage."""
        startup_delay = self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY)
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._boot_time).total_seconds()

        # Phase de démarrage : temporisation active si HA démarre encore ou délai non écoulé
        in_startup_phase = (
            self.hass.state != CoreState.running
            or elapsed_seconds < startup_delay
        )

        if in_startup_phase:
            remaining = max(0, int(startup_delay - elapsed_seconds))
            _LOGGER.debug(
                "HA Monitoring en phase d'initialisation (%s s restantes). Alertes masquées.",
                remaining,
            )
            return self._empty_results(in_startup_delay=True)

        _LOGGER.debug("Analyse système active par HA Monitoring.")

        options = self.entry.options

        # Collecte parallèle des métriques
        addons = await self._async_get_addons(options.get(CONF_EXCLUDED_ADDONS, []))
        integrations = self._get_failed_integrations(options.get(CONF_EXCLUDED_INTEGRATIONS, []))
        automations = self._get_trace_errors("automation", options.get(CONF_EXCLUDED_AUTOMATIONS, []))
        scripts = self._get_trace_errors("script", options.get(CONF_EXCLUDED_SCRIPTS, []))
        updates = self._get_pending_updates(options.get(CONF_EXCLUDED_UPDATES, []))
        repairs = self._get_pending_repairs(options.get(CONF_EXCLUDED_REPAIRS, []))
        unavailable = self._get_unavailable_entities(options.get(CONF_EXCLUDED_UNAVAILABLE, []))
        offline, offline_timeout = self._get_offline_devices(
            options.get(CONF_EXCLUDED_OFFLINE, []),
            options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT),
        )

        return {
            "in_startup_delay": False,
            "monitoring_addons": {"items": addons, "total": len(addons)},
            "monitoring_integrations": {"items": integrations, "total": len(integrations)},
            "monitoring_automations": {"items": automations, "total": len(automations)},
            "monitoring_scripts": {"items": scripts, "total": len(scripts)},
            "monitoring_updates": {"items": updates, "total": len(updates)},
            "monitoring_repairs": {"items": repairs, "total": len(repairs)},
            "monitoring_unavailable": {"items": unavailable, "total": len(unavailable)},
            "monitoring_offline": {
                "items": offline,
                "total": len(offline),
                "timeout": offline_timeout,
            },
        }

    def _empty_results(self, in_startup_delay: bool) -> dict:
        """Résultats neutres pendant la temporisation de démarrage."""
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
        }

    async def _async_get_addons(self, excluded: list) -> list:
        if not is_hassio_running(self.hass):
            return []
        client = self.hass.data.get("hassio")
        if not client:
            return []

        try:
            if hasattr(client, "async_get_addons_info"):
                addons_info = await client.async_get_addons_info()
            elif hasattr(client, "get_addons_info"):
                addons_info = await client.get_addons_info()
            else:
                return []

            addons = addons_info.get("addons", [])
            failed = []
            for addon in addons:
                name = addon.get("name", "")
                slug = addon.get("slug", "")
                if name in excluded or slug in excluded:
                    continue

                if (addon.get("watchdog", False) or addon.get("boot") == "auto") and addon.get("state") in ["stopped", "unknown"]:
                    failed.append(name or slug)
            return failed
        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring Addons : %s", err)
            return []

    def _get_failed_integrations(self, excluded: list) -> list:
        failed = []
        for entry in self.hass.config_entries.async_entries():
            if entry.state in INTEGRATION_ERROR_STATES:
                name = entry.title or entry.domain
                if name not in excluded and entry.domain not in excluded:
                    failed.append(name)
        return failed

    def _get_trace_errors(self, domain: str, excluded: list) -> list:
        trace_data = self.hass.data.get("trace", {})
        failed = []

        for key, traces in list(trace_data.items()):
            if not (key.startswith(f"{domain}.") or key.startswith(f"{domain} ")):
                continue
            if not traces:
                continue

            try:
                trace_list = list(traces.values()) if isinstance(traces, dict) else list(traces)
                if not trace_list:
                    continue
                latest_trace = trace_list[-1]
            except Exception:
                continue

            error = latest_trace.as_dict().get("error") if hasattr(latest_trace, "as_dict") else latest_trace.get("error") if isinstance(latest_trace, dict) else None

            if error:
                entity_id = key if key.startswith(f"{domain}.") else None
                friendly_name = None

                if entity_id:
                    if entity_id in excluded:
                        continue
                    state = self.hass.states.get(entity_id)
                    if state:
                        friendly_name = state.attributes.get("friendly_name") or entity_id

                if not friendly_name:
                    for state in self.hass.states.async_all(domain):
                        item_id = state.attributes.get("id")
                        if item_id is not None and str(item_id) in key:
                            if state.entity_id in excluded:
                                friendly_name = "EXCLUDED"
                                break
                            friendly_name = state.attributes.get("friendly_name") or state.entity_id
                            break

                if friendly_name == "EXCLUDED":
                    continue

                friendly_name = friendly_name or key
                if friendly_name not in excluded and friendly_name not in failed:
                    failed.append(friendly_name)

        return failed

    def _get_pending_updates(self, excluded: list) -> list:
        pending = []
        for state_obj in self.hass.states.async_all("update"):
            if state_obj.entity_id in excluded:
                continue
            if state_obj.state == "on":
                name = state_obj.attributes.get("friendly_name") or state_obj.entity_id
                if name not in pending:
                    pending.append(name)
        return pending

    def _get_pending_repairs(self, excluded: list) -> list:
        issue_registry = ir.async_get(self.hass)
        pending = []
        for issue in issue_registry.issues.values():
            if hasattr(issue, "active") and not issue.active:
                continue
            if getattr(issue, "dismissed_version", None) is not None:
                continue

            issue_name = f"{issue.domain}: {issue.issue_id}"
            if issue_name in excluded or issue.domain in excluded or issue.issue_id in excluded:
                continue
            if issue_name not in pending:
                pending.append(issue_name)
        return pending

    def _get_unavailable_entities(self, excluded: list) -> list:
        unavailable = []
        for state_obj in self.hass.states.async_all():
            if state_obj.entity_id in excluded:
                continue
            if state_obj.state == STATE_UNAVAILABLE:
                name = state_obj.attributes.get("friendly_name") or state_obj.entity_id
                if name not in unavailable:
                    unavailable.append(name)
        return unavailable

    def _get_offline_devices(self, excluded: list, timeout_hours: float) -> tuple[list, float]:
        now = dt_util.now()
        cutoff = now - timedelta(hours=float(timeout_hours))
        offline = []

        for state_obj in self.hass.states.async_all():
            if state_obj.entity_id in excluded or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue

            last_seen_dt = None
            entity_id = state_obj.entity_id

            if any(term in entity_id for term in ("last_seen", "derniere_connexion", "last_reported")):
                last_seen_dt = dt_util.parse_datetime(str(state_obj.state))

            if not last_seen_dt and state_obj.attributes:
                for attr_key in ("last_seen", "last_reported", "derniere_connexion", "last_seen_timestamp"):
                    val = state_obj.attributes.get(attr_key)
                    if val is not None:
                        if isinstance(val, (int, float)):
                            try:
                                ts = val / 1000.0 if val > 1e11 else float(val)
                                last_seen_dt = dt_util.utc_from_timestamp(ts)
                            except Exception:
                                pass
                        elif isinstance(val, str):
                            last_seen_dt = dt_util.parse_datetime(val)
                        elif isinstance(val, datetime):
                            last_seen_dt = val

                        if last_seen_dt:
                            break

            if last_seen_dt and dt_util.as_utc(last_seen_dt) < dt_util.as_utc(cutoff):
                name = state_obj.attributes.get("friendly_name") or entity_id
                if name not in offline:
                    offline.append(name)

        return offline, timeout_hours
