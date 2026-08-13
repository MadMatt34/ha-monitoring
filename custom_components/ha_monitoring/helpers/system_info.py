"""Collecteur d'informations système, métriques et Recorder pour HA Monitoring."""

from datetime import datetime
import logging
import os

from homeassistant.components.hassio import (
    HassioNotReadyError,
    get_host_info,
    get_os_info,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.util import dburl_to_path
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.translation import async_get_translations
from homeassistant.loader import async_get_custom_components
from homeassistant.util import dt as dt_util

from ..const import (
    DOMAIN,
    INTEGRATION_EXCLUDED_DOMAINS,
    INTEGRATION_VALID_STATES,
)
from ..types import RecorderData, SystemStatsData
from .utils import format_date_local

_LOGGER = logging.getLogger(__name__)


async def async_get_recorder_info(
    hass: HomeAssistant,
) -> RecorderData:
    """Récupère la configuration du Recorder et la taille de la base SQLite."""
    info: RecorderData = {
        "recorder_keep_days": None,
        "recorder_auto_purge": None,
        "recorder_auto_repack": None,
        "recorder_commit_interval": None,
        "database_size_mb": None,
    }

    instance = get_instance(hass)

    if instance is None:
        return info

    info["recorder_keep_days"] = instance.keep_days
    info["recorder_auto_purge"] = instance.auto_purge
    info["recorder_auto_repack"] = instance.auto_repack
    info["recorder_commit_interval"] = instance.commit_interval

    db_path = dburl_to_path(instance.db_url)

    def _get_db_size() -> float | None:
        """Retourne la taille de la base SQLite."""
        try:
            size_bytes = os.path.getsize(db_path)
        except OSError:
            return None

        return round(size_bytes / (1024 * 1024), 2)

    info["database_size_mb"] = await hass.async_add_executor_job(_get_db_size)

    return info


async def async_get_system_stats(
    hass: HomeAssistant,
    ha_start_time: datetime,
) -> SystemStatsData:
    """Collecte l'ensemble des métriques d'inventaire et du système."""
    ha_last_boot = format_date_local(ha_start_time)

    os_version: str | None = None
    os_boot_dt: datetime | None = None

    if is_hassio(hass):
        try:
            os_info = get_os_info(hass)
        except HassioNotReadyError:
            _LOGGER.debug("[HA Monitoring] Informations Home Assistant OS indisponibles.")
        else:
            os_version = os_info.get("version")

        try:
            host_info = get_host_info(hass)
        except HassioNotReadyError:
            _LOGGER.debug("[HA Monitoring] Informations de l'hôte Supervisor indisponibles.")
        else:
            boot_timestamp = host_info.get("boot_timestamp")

            if isinstance(boot_timestamp, int):
                os_boot_dt = dt_util.utc_from_timestamp(boot_timestamp / 1_000_000)

    translations = await async_get_translations(
        hass,
        hass.config.language,
        "system",
        integrations={DOMAIN},
    )

    unknown_text = translations[f"component.{DOMAIN}.system.unknown"]

    unknown_os_version_text = translations[f"component.{DOMAIN}.system.unknown_os_version"]

    os_last_boot = format_date_local(os_boot_dt) if os_boot_dt is not None else unknown_text

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    devices_count = sum(1 for device in dev_reg.devices.values() if device.disabled_by is None)

    entities_count = sum(
        1
        for entry in ent_reg.entities.values()
        if (entry.disabled_by is None and entry.domain not in ("script", "automation"))
    )

    automations_count = len(hass.states.async_all("automation"))

    scripts_count = len(hass.states.async_all("script"))

    active_entries = [
        entry
        for entry in hass.config_entries.async_entries()
        if (
            entry.state in INTEGRATION_VALID_STATES
            and entry.disabled_by is None
            and entry.domain not in INTEGRATION_EXCLUDED_DOMAINS
        )
    ]

    active_integration_domains = sorted({entry.domain for entry in active_entries})

    integrations_count = len(active_integration_domains)

    _LOGGER.debug(
        "[HA Monitoring] Domaines d'intégration comptabilisés (%d) : %s",
        integrations_count,
        active_integration_domains,
    )

    custom_components = await async_get_custom_components(hass)

    active_custom_domains = sorted(
        domain for domain in custom_components if domain in hass.config.components
    )

    custom_integrations_count = len(active_custom_domains)

    _LOGGER.debug(
        "[HA Monitoring] Intégrations personnalisées détectées (%d) : %s",
        custom_integrations_count,
        active_custom_domains,
    )

    recorder_info = await async_get_recorder_info(hass)

    return {
        "ha_version": HA_VERSION,
        "ha_last_boot": ha_last_boot,
        "os_version": (os_version or unknown_os_version_text),
        "os_last_boot": os_last_boot,
        "devices_count": devices_count,
        "entities_count": entities_count,
        "automations_count": automations_count,
        "scripts_count": scripts_count,
        "integrations_count": integrations_count,
        "custom_integrations_count": custom_integrations_count,
        **recorder_info,
    }
