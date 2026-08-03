"""Classe de base pour toutes les entités de HA Monitoring."""
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEVICE_NAME,
    DEVICE_MANUFACTURER,
)


class HAMonitoringBaseEntity(CoordinatorEntity):
    """Classe de base pour toutes les entités de HA Monitoring."""

    def __init__(self, coordinator) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Retourne les informations du Device unique."""
        # Tente de récupérer l'URL externe en priorité, sinon bascule sur l'interne
        try:
            config_url = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            config_url = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"Core {HA_VERSION}",
            configuration_url=config_url,
        )
