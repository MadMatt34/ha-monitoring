"""Capteurs HA Monitoring alimentés par le Coordinator central."""

from collections.abc import Callable
from typing import Any, override

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
from .types import (
    HAMonitoringData,
    MonitoringAddonData,
    MonitoringIntegrationData,
    MonitoringOfflineData,
    MonitoringRepairData,
    MonitoringTraceData,
    MonitoringUnavailableData,
    MonitoringUpdateData,
)

type SensorData = (
    MonitoringAddonData
    | MonitoringIntegrationData
    | MonitoringTraceData
    | MonitoringUpdateData
    | MonitoringRepairData
    | MonitoringUnavailableData
    | MonitoringOfflineData
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute l'ensemble des capteurs de surveillance."""
    coordinator: HAMonitoringCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[HAMonitoringGenericSensor[SensorData]] = [
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_addons"],
            unique_key=UNIQUE_ID_ADDONS,
            translation_key=TRANSLATION_KEY_ADDONS,
            icon=ICON_ADDONS,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_integrations"],
            unique_key=UNIQUE_ID_INTEGRATIONS,
            translation_key=TRANSLATION_KEY_INTEGRATIONS,
            icon=ICON_INTEGRATIONS,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_automations"],
            unique_key=UNIQUE_ID_AUTOMATIONS,
            translation_key=TRANSLATION_KEY_AUTOMATIONS,
            icon=ICON_AUTOMATIONS,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_scripts"],
            unique_key=UNIQUE_ID_SCRIPTS,
            translation_key=TRANSLATION_KEY_SCRIPTS,
            icon=ICON_SCRIPTS,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_updates"],
            unique_key=UNIQUE_ID_UPDATES,
            translation_key=TRANSLATION_KEY_UPDATES,
            icon=ICON_UPDATES,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_repairs"],
            unique_key=UNIQUE_ID_REPAIRS,
            translation_key=TRANSLATION_KEY_REPAIRS,
            icon=ICON_REPAIRS,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_unavailable"],
            unique_key=UNIQUE_ID_UNAVAILABLE,
            translation_key=TRANSLATION_KEY_UNAVAILABLE,
            icon=ICON_UNAVAILABLE,
        ),
        HAMonitoringGenericSensor(
            coordinator=coordinator,
            entry=entry,
            data_getter=lambda data: data["monitoring_offline"],
            unique_key=UNIQUE_ID_OFFLINE,
            translation_key=TRANSLATION_KEY_OFFLINE,
            icon=ICON_OFFLINE,
            extra_attributes=lambda data: {
                "seuil_timeout": data["timeout"],
            },
        ),
    ]

    async_add_entities(sensors)


class HAMonitoringGenericSensor[T: SensorData](
    HAMonitoringBaseEntity,
    SensorEntity,
):
    """Capteur générique lié au DataUpdateCoordinator."""

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: ConfigEntry,
        data_getter: Callable[[HAMonitoringData], T],
        unique_key: str,
        translation_key: str,
        icon: str,
        extra_attributes: Callable[[T], dict[str, object]]
        | None = None,
    ) -> None:
        """Initialise le capteur générique."""
        super().__init__(coordinator)

        self._data_getter = data_getter
        self._extra_attributes_getter = extra_attributes

        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{unique_key}"

        # Entity ID volontairement statique et indépendant du ConfigEntry.
        self.entity_id = f"sensor.{unique_key}"

    @property
    def _sensor_data(self) -> T:
        """Retourne le bloc de données typé du capteur."""
        return self._data_getter(self.coordinator.data)

    @override
    @property
    def native_value(self) -> int:
        """Retourne le nombre total d'éléments détectés."""
        if self.coordinator.data["startup_delay"]:
            return 0

        return self._sensor_data["total"]

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Retourne les détails et métadonnées du capteur."""
        data = self._sensor_data

        attributes: dict[str, Any] = {
            ATTR_LIST: data["items"],
            ATTR_TOTAL: data["total"],
            ATTR_STARTUP_DELAY: self.coordinator.data["startup_delay"],
        }

        if self._extra_attributes_getter is not None:
            attributes.update(
                self._extra_attributes_getter(data)
            )

        return attributes
