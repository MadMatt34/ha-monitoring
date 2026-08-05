"""Capteurs HA Monitoring alimentés par le Coordinator central."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LIST,
    ATTR_STARTUP_DELAY,
    ATTR_TOTAL,
    DOMAIN,
    ICON_ADDONS,
    ICON_AUTOMATIONS,
    ICON_INTEGRATIONS,
    ICON_OFFLINE,
    ICON_REPAIRS,
    ICON_SCRIPTS,
    ICON_UNAVAILABLE,
    ICON_UPDATES,
    TRANSLATION_KEY_ADDONS,
    TRANSLATION_KEY_AUTOMATIONS,
    TRANSLATION_KEY_INTEGRATIONS,
    TRANSLATION_KEY_OFFLINE,
    TRANSLATION_KEY_REPAIRS,
    TRANSLATION_KEY_SCRIPTS,
    TRANSLATION_KEY_UNAVAILABLE,
    TRANSLATION_KEY_UPDATES,
    UNIQUE_ID_ADDONS,
    UNIQUE_ID_AUTOMATIONS,
    UNIQUE_ID_INTEGRATIONS,
    UNIQUE_ID_OFFLINE,
    UNIQUE_ID_REPAIRS,
    UNIQUE_ID_SCRIPTS,
    UNIQUE_ID_UNAVAILABLE,
    UNIQUE_ID_UPDATES,
)
from .coordinator import HAMonitoringCoordinator
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger("custom_components.ha_monitoring.sensor")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute l'ensemble des capteurs de surveillance à partir du Coordinator."""
    coordinator: HAMonitoringCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_addons",
            unique_key=UNIQUE_ID_ADDONS,
            translation_key=TRANSLATION_KEY_ADDONS,
            icon=ICON_ADDONS,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_integrations",
            unique_key=UNIQUE_ID_INTEGRATIONS,
            translation_key=TRANSLATION_KEY_INTEGRATIONS,
            icon=ICON_INTEGRATIONS,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_automations",
            unique_key=UNIQUE_ID_AUTOMATIONS,
            translation_key=TRANSLATION_KEY_AUTOMATIONS,
            icon=ICON_AUTOMATIONS,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_scripts",
            unique_key=UNIQUE_ID_SCRIPTS,
            translation_key=TRANSLATION_KEY_SCRIPTS,
            icon=ICON_SCRIPTS,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_updates",
            unique_key=UNIQUE_ID_UPDATES,
            translation_key=TRANSLATION_KEY_UPDATES,
            icon=ICON_UPDATES,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_repairs",
            unique_key=UNIQUE_ID_REPAIRS,
            translation_key=TRANSLATION_KEY_REPAIRS,
            icon=ICON_REPAIRS,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_unavailable",
            unique_key=UNIQUE_ID_UNAVAILABLE,
            translation_key=TRANSLATION_KEY_UNAVAILABLE,
            icon=ICON_UNAVAILABLE,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
        ),
        HAMonitoringGenericSensor(
            coordinator,
            entry,
            data_key="monitoring_offline",
            unique_key=UNIQUE_ID_OFFLINE,
            translation_key=TRANSLATION_KEY_OFFLINE,
            icon=ICON_OFFLINE,
            list_attr=ATTR_LIST,
            total_attr=ATTR_TOTAL,
            extra_keys=["timeout"],
        ),
    ]

    async_add_entities(sensors)


class HAMonitoringGenericSensor(HAMonitoringBaseEntity, SensorEntity):
    """Capteur générique lié au DataUpdateCoordinator de HA Monitoring."""

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: ConfigEntry,
        data_key: str,
        unique_key: str,
        translation_key: str,
        icon: str,
        list_attr: str,
        total_attr: str,
        extra_keys: list[str] | None = None,
    ) -> None:
        """Initialise le capteur générique."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._list_attr = list_attr
        self._total_attr = total_attr
        self._extra_keys = extra_keys or []

        self._attr_unique_id = f"{entry.entry_id}_{unique_key}"
        self.entity_id = f"sensor.{unique_key}"

    @property
    def native_value(self) -> int:
        """Retourne le nombre total d'éléments détectés."""
        if not self.coordinator.data:
            return 0
        data = self.coordinator.data.get(self._data_key, {})
        return data.get("total", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Retourne la liste détaillée et les métadonnées."""
        if not self.coordinator.data:
            return {
                self._list_attr: [],
                self._total_attr: 0,
                ATTR_STARTUP_DELAY: True,
            }

        data = self.coordinator.data.get(self._data_key, {})
        items = data.get("items", [])
        total = data.get("total", 0)

        attrs: dict[str, Any] = {
            self._list_attr: items,
            self._total_attr: total,
            ATTR_STARTUP_DELAY: self.coordinator.data.get("in_startup_delay", False),
        }

        for key in self._extra_keys:
            if key in data:
                attrs[f"seuil_{key}"] = data[key]

        return attrs