"""Intégration HA Monitoring pour la surveillance système."""
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Configuration initiale de l'intégration HA Monitoring."""
    for platform in ["sensor", "binary_sensor"]:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config)
        )
    return True
