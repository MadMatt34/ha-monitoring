"""Support pour la plateforme button de HA Monitoring."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HAMonitoringCoordinator
from .entity import HAMonitoringBaseEntity
from .const import (
    DOMAIN,
    ICON_REFRESH,
    UNIQUE_ID_REFRESH,
    TRANSLATION_KEY_REFRESH,
)

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

    _attr_translation_key = TRANSLATION_KEY_REFRESH
    _attr_icon = ICON_REFRESH

    def __init__(self, coordinator: HAMonitoringCoordinator, entry: ConfigEntry) -> None:
        """Initialisation du bouton."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_REFRESH}"
        self.entity_id = f"button.{UNIQUE_ID_REFRESH}"

    async def async_press(self) -> None:
        """Gère l'appui sur le bouton."""
        _LOGGER.info("Bouton appuyé : lancement d'un rafraîchissement forcé de HA Monitoring.")
        await self.coordinator.async_force_refresh()
