"""Support pour la plateforme button de HA Monitoring."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ICON_REFRESH,
    TRANSLATION_KEY_REFRESH,
    UNIQUE_ID_REFRESH,
)
from .coordinator import HAMonitoringCoordinator
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger("custom_components.ha_monitoring.button")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configuration de la plateforme button à partir d'une ConfigEntry."""
    coordinator: HAMonitoringCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HAMonitoringForceScanButton(coordinator, entry)])


class HAMonitoringForceScanButton(HAMonitoringBaseEntity, ButtonEntity):
    """Bouton permettant de forcer le rafraîchissement de HA Monitoring."""

    _attr_translation_key = TRANSLATION_KEY_REFRESH
    _attr_icon = ICON_REFRESH

    def __init__(self, coordinator: HAMonitoringCoordinator, entry: ConfigEntry) -> None:
        """Initialisation du bouton."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_REFRESH}"
        self.entity_id = f"button.{UNIQUE_ID_REFRESH}"

    async def async_press(self) -> None:
        """Gère l'appui sur le bouton."""
        _LOGGER.info("[HA Monitoring] Bouton appuyé : rafraîchissement forcé en cours.")
        await self.coordinator.async_force_refresh()
