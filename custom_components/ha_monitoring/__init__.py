"""Intégration HA Monitoring pour la surveillance système."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HAMonitoringCoordinator  # Import du coordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Configuration initiale (legacy yaml)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialisation de l'intégration depuis l'UI."""
    hass.data.setdefault(DOMAIN, {})

    # 1. Instanciation du coordinator
    coordinator = HAMonitoringCoordinator(hass, entry)

    # 2. Premier rafraîchissement des données au chargement
    await coordinator.async_config_entry_first_refresh()

    # 3. Stockage de l'instance pour que sensor.py puisse y accéder
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Recharger automatiquement l'intégration si l'utilisateur change les options dans l'UI
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Déchargement de l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge les entités avec le nouvel intervalle."""
    await hass.config_entries.async_reload(entry.entry_id)
