"""Intégration HA Monitoring pour la surveillance système."""
import logging

DOMAIN = "ha_monitoring"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Configuration initiale de l'intégration HA Monitoring."""
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )
    return True
