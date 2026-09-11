"""Switch de maintenance pour HA Monitoring."""

from typing import override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ICON_MAINTENANCE,
    TRANSLATION_KEY_MAINTENANCE,
    UNIQUE_ID_MAINTENANCE,
)
from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)
from .entity import HAMonitoringBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute le switch de maintenance."""
    async_add_entities(
        [
            MaintenanceSwitch(
                entry.runtime_data,
                entry,
            )
        ]
    )


class MaintenanceSwitch(
    HAMonitoringBaseEntity,
    SwitchEntity,
):
    """Switch permettant d'activer le mode maintenance."""

    _attr_translation_key = (
        TRANSLATION_KEY_MAINTENANCE
    )
    _attr_icon = ICON_MAINTENANCE

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: HAMonitoringConfigEntry,
    ) -> None:
        """Initialise le switch."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.entry_id}_{UNIQUE_ID_MAINTENANCE}"
        )

        self.entity_id = (
            f"switch.{UNIQUE_ID_MAINTENANCE}"
        )

    @override
    @property
    def is_on(self) -> bool:
        """Retourne l'état du mode maintenance."""
        return self.coordinator.maintenance_mode

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Active le mode maintenance."""
        await self.coordinator.async_set_maintenance_mode(
            True
        )

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Désactive le mode maintenance."""
        await self.coordinator.async_set_maintenance_mode(
            False
        )
