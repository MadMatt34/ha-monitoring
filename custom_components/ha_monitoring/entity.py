"""Classe de base pour toutes les entités de HA Monitoring."""

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DEVICE_NAME, DOMAIN
from .coordinator import HAMonitoringCoordinator


class HAMonitoringBaseEntity(
    CoordinatorEntity[HAMonitoringCoordinator]
):
    """Classe de base pour toutes les entités de HA Monitoring."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
    ) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)
        self._cached_device_info: DeviceInfo | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Retourne les informations de l'appareil unique en cache."""
        if self._cached_device_info is not None:
            return self._cached_device_info

        config_url: str | None = None

        if self.hass:
            try:
                config_url = get_url(
                    self.hass,
                    prefer_external=True,
                )
            except NoURLAvailableError:
                config_url = None

        self._cached_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"Core {HA_VERSION}",
            configuration_url=config_url,
        )

        return self._cached_device_info
