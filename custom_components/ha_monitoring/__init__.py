"""Intégration HA Monitoring pour la surveillance système."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HAMonitoringCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform | str] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Configuration initiale via YAML (non supportée / legacy)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialisation de l'intégration depuis une ConfigEntry UI."""
    hass.data.setdefault(DOMAIN, {})

    # Instanciation du coordinator
    coordinator = HAMonitoringCoordinator(hass, entry)

    # Premier rafraîchissement des données au chargement
    await coordinator.async_config_entry_first_refresh()

    # Stockage du coordinator pour l'accès depuis les plateformes et backup.py
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Rechargement automatique lors de la modification des options dans l'UI
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Chargement des plateformes (Sensor, Binary Sensor, Button, Backup)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Déchargement des plateformes et nettoyage des ressources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HAMonitoringCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_shutdown()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'intégration lors d'un changement de configuration."""
    await hass.config_entries.async_reload(entry.entry_id)
