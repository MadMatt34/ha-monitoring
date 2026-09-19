"""Intégration HA Monitoring pour la surveillance système."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STORAGE_KEY_MAINTENANCE,
    STORAGE_VERSION_MAINTENANCE,
)
from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Configuration initiale via YAML."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Initialise l'intégration depuis une ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HAMonitoringCoordinator(
        hass,
        entry,
    )

    entry.runtime_data = coordinator

    # Le cleanup doit être enregistré AVANT le first_refresh().
    entry.async_on_unload(coordinator.async_shutdown)

    # Charger les données persistantes avant le premier refresh.
    await coordinator.async_initialize()

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Décharge les plateformes de l'intégration."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )


async def async_remove_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> None:
    """Supprime les données globales associées à la ConfigEntry."""
    domain_data = hass.data.get(DOMAIN)

    if domain_data is not None:
        backup_cache = domain_data.get("backup_cache")
        if isinstance(backup_cache, dict):
            backup_cache.pop(
                entry.entry_id,
                None,
            )

            if not backup_cache:
                domain_data.pop(
                    "backup_cache",
                    None,
                )

        backup_scan_timestamp_cache = domain_data.get("backup_scan_timestamp_cache")
        if isinstance(backup_scan_timestamp_cache, dict):
            backup_scan_timestamp_cache.pop(
                entry.entry_id,
                None,
            )

            if not backup_scan_timestamp_cache:
                domain_data.pop(
                    "backup_scan_timestamp_cache",
                    None,
                )

        backup_scan_duration_cache = domain_data.get("backup_scan_duration_cache")
        if isinstance(backup_scan_duration_cache, dict):
            backup_scan_duration_cache.pop(
                entry.entry_id,
                None,
            )

            if not backup_scan_duration_cache:
                domain_data.pop(
                    "backup_scan_duration_cache",
                    None,
                )

    maintenance_store: Store[dict[str, bool]] = Store(
        hass,
        STORAGE_VERSION_MAINTENANCE,
        STORAGE_KEY_MAINTENANCE,
    )

    stored_data = (await maintenance_store.async_load()) or {}

    if entry.entry_id in stored_data:
        stored_data.pop(entry.entry_id)
        await maintenance_store.async_save(stored_data)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> None:
    """Recharge l'intégration."""
    await hass.config_entries.async_reload(entry.entry_id)
