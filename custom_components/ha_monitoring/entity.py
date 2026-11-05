"""Classe de base pour toutes les entités de HA Monitoring."""

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DEVICE_NAME, DOMAIN
from .coordinator import HAMonitoringCoordinator


class HAMonitoringBaseEntity(CoordinatorEntity[HAMonitoringCoordinator]):
    """Classe de base pour toutes les entités de HA Monitoring."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Retourne les informations de l'appareil Home Assistant."""
        config_url: str | None = None

        try:
            config_url = get_url(
                self.hass,
                prefer_external=True,
            )
        except NoURLAvailableError:
            pass

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"Core {HA_VERSION}",
            configuration_url=config_url,
        )
