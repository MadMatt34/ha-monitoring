"""Classe de base pour toutes les entités de HA Monitoring."""

import logging

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_NAME,
    DOMAIN,
)
from .coordinator import HAMonitoringCoordinator

_LOGGER = logging.getLogger("custom_components.ha_monitoring.entity")


class HAMonitoringBaseEntity(CoordinatorEntity[HAMonitoringCoordinator]):
    """Classe de base pour toutes les entités de HA Monitoring."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HAMonitoringCoordinator) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Retourne les informations de l'appareil (Device) unique."""
        config_url: str | None = None
        if self.hass:
            try:
                config_url = get_url(self.hass, prefer_external=True)
            except NoURLAvailableError:
                config_url = None
            except Exception as err:
                _LOGGER.debug("[HA Monitoring] Erreur récupération URL réseau : %s", err)
                config_url = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"Core {HA_VERSION}",
            configuration_url=config_url,
        )