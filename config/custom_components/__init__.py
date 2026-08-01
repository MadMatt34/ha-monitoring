"""Intégration de surveillance des erreurs d'add-ons Supervisor."""
import logging

DOMAIN = "supervisor_addon_monitor"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Configuration initiale de l'intégration."""
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )
    return True
