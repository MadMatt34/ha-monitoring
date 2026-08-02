"""Support pour la plateforme button de HA Monitoring."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HAMonitoringCoordinator
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger(__name__)


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

    _attr_translation_key = "force_scan"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: HAMonitoringCoordinator, entry: ConfigEntry) -> None:
        """Initialisation du bouton."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_force_scan"

    async def async_press(self) -> None:
        """Gère l'appui sur le bouton."""
        _LOGGER.info("Bouton appuyé : lancement d'un rafraîchissement forcé de HA Monitoring.")
        await self.coordinator.async_force_refresh()
