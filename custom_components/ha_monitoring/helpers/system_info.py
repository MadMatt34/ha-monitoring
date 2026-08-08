"""Collecteur d'informations système, métriques et Recorder pour HA Monitoring."""

from datetime import datetime, timedelta
import logging
import os
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.loader import async_get_custom_components
from homeassistant.util import dt as dt_util

from .utils import format_date_local, is_hassio_running

_LOGGER = logging.getLogger("custom_components.ha_monitoring.system_info")

VALID_ENTRY_STATES = {
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.FAILED_UNLOAD,
    ConfigEntryState.SETUP_IN_PROGRESS,
}

EXCLUDED_INTEGRATION_DOMAINS = {
    # Helpers / Entrées d'aide
    "group", "utility_meter", "threshold", "min_max", "template",
    "tod", "derivative", "integral", "compensation", "filter",
    "generic_thermostat", "generic_hygrostat", "timer", "counter",
    "input_boolean", "input_button", "input_datetime", "input_number",
    "input_select", "input_text", "schedule", "bayesian", "trend",
    "go2rtc", "statistics", "switch_as_x",
    # Système / Interne
    "hardware", "diagnostics", "analytics", "homeassistant", "integration",
}


def _get_host_boot_from_uptime() -> datetime | None:
    """Calcule la date de démarrage de l'hôte via /proc/uptime en secours."""
    try:
        if os.path.exists("/proc/uptime"):
            with open("/proc/uptime") as f:
                uptime_sec = float(f.readline().split()[0])
            return dt_util.utcnow() - timedelta(seconds=uptime_sec)
    except Exception as err:
        _LOGGER.debug("[HA Monitoring] Erreur lecture /proc/uptime : %s", err)
    return None


async def async_get_recorder_info(hass: HomeAssistant) -> dict[str, Any]:
    """Récupère la configuration du Recorder et la taille de la base de données."""
    info = {
        "recorder_keep_days": None,
        "recorder_auto_purge": None,
        "recorder_auto_repack": None,
        "recorder_commit_interval": None,
        "database_size_mb": None,
    }

    try:
        instance = get_instance(hass)
        if instance:
            info["recorder_keep_days"] = getattr(instance, "keep_days", None) or getattr(instance, "purge_keep_days", None)
            info["recorder_auto_purge"] = getattr(instance, "auto_purge", None)
            info["recorder_auto_repack"] = getattr(instance, "auto_repack", None)
            info["recorder_commit_interval"] = getattr(instance, "commit_interval", None)

            def _get_db_size() -> float | None:
                db_url = getattr(instance, "db_url", None)
                db_path = None

                if db_url and "sqlite" in db_url:
                    path_part = db_url.split(":///")[-1]
                    db_path = path_part if os.path.isabs(path_part) else hass.config.path(path_part)

                if not db_path or not os.path.exists(db_path):
                    db_path = hass.config.path("home-assistant_v2.db")

                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    return round(size_bytes / (1024 * 1024), 2)
                return None

            info["database_size_mb"] = await hass.async_add_executor_job(_get_db_size)
    except Exception as err:
        _LOGGER.debug("[HA Monitoring] Erreur lors de la lecture du Recorder : %s", err)

    return info


async def async_get_system_stats(
    hass: HomeAssistant, ha_start_time: datetime
) -> dict[str, Any]:
    """Collecte l'ensemble des métriques d'inventaire et du système."""
    ha_last_boot = format_date_local(ha_start_time)

    os_version = None
    os_boot_dt = None

    if is_hassio_running(hass):
        try:
            from homeassistant.components.hassio import async_get_host_info, async_get_os_info

            os_info = await async_get_os_info(hass)
            if isinstance(os_info, dict):
                os_version = os_info.get("version")

            host_info = await async_get_host_info(hass)
            if isinstance(host_info, dict):
                if not os_version:
                    os_version = host_info.get("operating_system")

                boot_ts = host_info.get("boot_timestamp")
                if boot_ts:
                    ts_sec = boot_ts / 1000000.0 if boot_ts > 1e11 else float(boot_ts)
                    os_boot_dt = datetime.fromtimestamp(ts_sec, tz=dt_util.UTC)
        except Exception as err:
            _LOGGER.debug("[HA Monitoring] Échec des helpers hassio : %s", err)

        if not os_version or not os_boot_dt:
            client = hass.data.get("hassio")
            if client and hasattr(client, "send_command"):
                if not os_version:
                    try:
                        res_os = await client.send_command("/os/info")
                        if isinstance(res_os, dict) and res_os.get("result") == "ok":
                            os_version = res_os.get("data", {}).get("version")
                    except Exception as err:
                        _LOGGER.debug("[HA Monitoring] Échec API /os/info : %s", err)

                try:
                    res_host = await client.send_command("/host/info")
                    if isinstance(res_host, dict) and res_host.get("result") == "ok":
                        data_host = res_host.get("data", {})
                        if not os_version:
                            os_version = data_host.get("operating_system")

                        if not os_boot_dt:
                            boot_ts = data_host.get("boot_timestamp")
                            if boot_ts:
                                ts_sec = boot_ts / 1000000.0 if boot_ts > 1e11 else float(boot_ts)
                                os_boot_dt = datetime.fromtimestamp(ts_sec, tz=dt_util.UTC)
                except Exception as err:
                    _LOGGER.debug("[HA Monitoring] Échec API /host/info : %s", err)

        if not os_version:
            for state in hass.states.async_all("update"):
                if "os" in state.entity_id or "operating_system" in state.entity_id:
                    installed = state.attributes.get("installed_version")
                    if installed:
                        os_version = str(installed)
                        break

    if not os_boot_dt:
        os_boot_dt = await hass.async_add_executor_job(_get_host_boot_from_uptime)

    os_last_boot = format_date_local(os_boot_dt) if os_boot_dt else "Inconnu"

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    devices_count = sum(
        1 for device in dev_reg.devices.values()
        if device.disabled_by is None
    )

    entities_count = sum(
        1 for entry in ent_reg.entities.values()
        if entry.disabled_by is None
        and entry.domain not in ("script", "automation")
    )

    automations_count = len(hass.states.async_all("automation"))
    scripts_count = len(hass.states.async_all("script"))

    active_entries = [
        e for e in hass.config_entries.async_entries()
        if e.state in VALID_ENTRY_STATES
        and getattr(e, "disabled_by", None) is None
        and e.domain not in EXCLUDED_INTEGRATION_DOMAINS
    ]

    active_integration_domains = sorted(list({e.domain for e in active_entries}))
    integrations_count = len(active_integration_domains)

    _LOGGER.debug(
        "[HA Monitoring] Domaines d'intégration comptabilisés (%d) : %s",
        integrations_count,
        active_integration_domains,
    )

    try:
        custom_components = await async_get_custom_components(hass)
        active_custom_domains = sorted([
            domain for domain in custom_components
            if domain in hass.config.components
        ])
        custom_integrations_count = len(active_custom_domains)

        _LOGGER.debug(
            "[HA Monitoring] Intégrations personnalisées détectées (%d) : %s",
            custom_integrations_count,
            active_custom_domains,
        )
    except Exception as err:
        _LOGGER.warning("[HA Monitoring] Erreur lors du comptage des custom components : %s", err)
        custom_integrations_count = 0

    recorder_info = await async_get_recorder_info(hass)

    return {
        "ha_version": HA_VERSION,
        "ha_last_boot": ha_last_boot,
        "os_version": os_version or "N/A (Core/Container)",
        "os_last_boot": os_last_boot,
        "devices_count": devices_count,
        "entities_count": entities_count,
        "automations_count": automations_count,
        "scripts_count": scripts_count,
        "integrations_count": integrations_count,
        "custom_integrations_count": custom_integrations_count,
        **recorder_info,
    }