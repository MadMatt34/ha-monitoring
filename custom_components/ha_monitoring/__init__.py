"""Intégration HA Monitoring pour la surveillance système."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_EVENT_ADDONS_DECREASE,
    CONF_EVENT_ADDONS_INCREASE,
    CONF_EVENT_AUTOMATIONS_DECREASE,
    CONF_EVENT_AUTOMATIONS_INCREASE,
    CONF_EVENT_BATTERY_DECREASE,
    CONF_EVENT_BATTERY_INCREASE,
    CONF_EVENT_INTEGRATIONS_DECREASE,
    CONF_EVENT_INTEGRATIONS_INCREASE,
    CONF_EVENT_OFFLINE_DECREASE,
    CONF_EVENT_OFFLINE_INCREASE,
    CONF_EVENT_REPAIRS_DECREASE,
    CONF_EVENT_REPAIRS_INCREASE,
    CONF_EVENT_SCRIPTS_DECREASE,
    CONF_EVENT_SCRIPTS_INCREASE,
    CONF_EVENT_UNAVAILABLE_DECREASE,
    CONF_EVENT_UNAVAILABLE_INCREASE,
    CONF_EVENT_UPDATES_DECREASE,
    CONF_EVENT_UPDATES_INCREASE,
    DOMAIN,
    EVENT_CHANGE_DECREASED,
    EVENT_CHANGE_INCREASED,
    EVENT_NAME,
    EVENT_TYPE_COUNTER_CHANGED,
    STORAGE_KEY_MAINTENANCE,
    STORAGE_VERSION_MAINTENANCE,
    UNIQUE_ID_ADDONS,
    UNIQUE_ID_AUTOMATIONS,
    UNIQUE_ID_BATTERY,
    UNIQUE_ID_INTEGRATIONS,
    UNIQUE_ID_OFFLINE,
    UNIQUE_ID_REPAIRS,
    UNIQUE_ID_SCRIPTS,
    UNIQUE_ID_UNAVAILABLE,
    UNIQUE_ID_UPDATES,
)
from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)
from .types import HAMonitoringData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]


def _get_monitoring_counter_totals(
    data: HAMonitoringData,
) -> dict[str, int]:
    """Retourne les neuf compteurs fonctionnels de supervision."""
    return {
        "applications": data["monitoring_addons"]["total"],
        "integrations": data["monitoring_integrations"]["total"],
        "automations": data["monitoring_automations"]["total"],
        "scripts": data["monitoring_scripts"]["total"],
        "updates": data["monitoring_updates"]["total"],
        "repairs": data["monitoring_repairs"]["total"],
        "unavailable_entities": data["monitoring_unavailable"]["total"],
        "offline_devices": data["monitoring_offline"]["total"],
        "low_battery": data["monitoring_battery"]["total"],
    }


_EVENT_COUNTER_SETTINGS: dict[str, tuple[str, str, str]] = {
    "applications": (
        f"sensor.{UNIQUE_ID_ADDONS}",
        CONF_EVENT_ADDONS_INCREASE,
        CONF_EVENT_ADDONS_DECREASE,
    ),
    "integrations": (
        f"sensor.{UNIQUE_ID_INTEGRATIONS}",
        CONF_EVENT_INTEGRATIONS_INCREASE,
        CONF_EVENT_INTEGRATIONS_DECREASE,
    ),
    "automations": (
        f"sensor.{UNIQUE_ID_AUTOMATIONS}",
        CONF_EVENT_AUTOMATIONS_INCREASE,
        CONF_EVENT_AUTOMATIONS_DECREASE,
    ),
    "scripts": (
        f"sensor.{UNIQUE_ID_SCRIPTS}",
        CONF_EVENT_SCRIPTS_INCREASE,
        CONF_EVENT_SCRIPTS_DECREASE,
    ),
    "updates": (
        f"sensor.{UNIQUE_ID_UPDATES}",
        CONF_EVENT_UPDATES_INCREASE,
        CONF_EVENT_UPDATES_DECREASE,
    ),
    "repairs": (
        f"sensor.{UNIQUE_ID_REPAIRS}",
        CONF_EVENT_REPAIRS_INCREASE,
        CONF_EVENT_REPAIRS_DECREASE,
    ),
    "unavailable_entities": (
        f"sensor.{UNIQUE_ID_UNAVAILABLE}",
        CONF_EVENT_UNAVAILABLE_INCREASE,
        CONF_EVENT_UNAVAILABLE_DECREASE,
    ),
    "offline_devices": (
        f"sensor.{UNIQUE_ID_OFFLINE}",
        CONF_EVENT_OFFLINE_INCREASE,
        CONF_EVENT_OFFLINE_DECREASE,
    ),
    "low_battery": (
        f"sensor.{UNIQUE_ID_BATTERY}",
        CONF_EVENT_BATTERY_INCREASE,
        CONF_EVENT_BATTERY_DECREASE,
    ),
}


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

    previous_totals: dict[str, int] | None = None

    @callback
    def _handle_monitoring_update() -> None:
        """Déclenche les événements lorsque les compteurs changent."""
        nonlocal previous_totals

        data = coordinator.data
        if data is None:
            return

        current_totals = _get_monitoring_counter_totals(data)

        # Le premier scan utile établit uniquement la référence.
        # Le délai de démarrage et le mode maintenance ne doivent
        # produire aucun événement artificiel.
        if data["startup_delay"] or coordinator.maintenance_mode:
            previous_totals = None
            return

        if previous_totals is None:
            previous_totals = current_totals
            return

        for counter, current in current_totals.items():
            previous = previous_totals[counter]

            if current == previous:
                continue

            if current > previous:
                change = EVENT_CHANGE_INCREASED
                option_key = _EVENT_COUNTER_SETTINGS[counter][1]
            else:
                change = EVENT_CHANGE_DECREASED
                option_key = _EVENT_COUNTER_SETTINGS[counter][2]

            if not entry.options.get(option_key, False):
                continue

            hass.bus.async_fire(
                EVENT_NAME,
                {
                    "type": EVENT_TYPE_COUNTER_CHANGED,
                    "counter": counter,
                    "change": change,
                    "previous": previous,
                    "current": current,
                    "delta": current - previous,
                    "entity_id": _EVENT_COUNTER_SETTINGS[counter][0],
                },
            )

        previous_totals = current_totals

    # Le cleanup doit être enregistré AVANT le first_refresh().
    entry.async_on_unload(coordinator.async_shutdown)
    entry.async_on_unload(coordinator.async_add_listener(_handle_monitoring_update))

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
