"""Intégration HA Monitoring pour la surveillance système."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HAMonitoringConfigEntry, HAMonitoringCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform | str] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Configuration initiale via YAML (non supportée / legacy)."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Initialise l'intégration depuis une ConfigEntry UI."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HAMonitoringCoordinator(
        hass,
        entry,
    )

    # Le coordinator appartient au runtime de cette ConfigEntry.
    entry.runtime_data = coordinator

    # Premier rafraîchissement des données au chargement.
    await coordinator.async_config_entry_first_refresh()

    # Rechargement automatique lors de la modification des options dans l'UI.
    entry.async_on_unload(
        entry.add_update_listener(async_reload_entry)
    )

    # Chargement des plateformes.
    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Décharge les plateformes et nettoie les ressources."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        await entry.runtime_data.async_shutdown()

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Nettoie les données runtime globales lors de la suppression."""
    domain_data = hass.data.get(DOMAIN)

    if domain_data is None:
        return

    backup_cache = domain_data.get("backup_cache")

    if isinstance(backup_cache, dict):
        backup_cache.pop(entry.entry_id, None)

        if not backup_cache:
            domain_data.pop("backup_cache", None)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Recharge l'intégration lors d'un changement de configuration."""
    await hass.config_entries.async_reload(entry.entry_id)
