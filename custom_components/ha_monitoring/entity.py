from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class HAMonitoringBaseEntity(CoordinatorEntity):
    """Classe de base pour toutes les entités de HA Monitoring."""

    def __init__(self, coordinator) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)
        # Permet à HA de préfixer le nom de l'entité avec le nom du Device ("Home Assistant ...")
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Retourne les informations du Device unique."""
        # Récupération sécurisée de l'URL de l'instance Home Assistant
        try:
            config_url = get_url(self.hass)
        except NoURLAvailableError:
            config_url = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="Home Assistant",
            manufacturer="Home Assistant Community",
            model=f"Core {HA_VERSION}",
            configuration_url=config_url,
        )
