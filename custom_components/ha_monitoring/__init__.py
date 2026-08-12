"""Intégration HA Monitoring pour la surveillance système."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HAMonitoringConfigEntry, HAMonitoringCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "button",
]


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Configure l'intégration."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Initialise l'intégration depuis une ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HAMonitoringCoordinator(
        hass,
        entry,
    )

    # Le coordinator est une donnée runtime de cette ConfigEntry.
    entry.runtime_data = coordinator

    # Le cleanup doit être enregistré AVANT le first_refresh().
    # Cela garantit le nettoyage du coordinator si le premier refresh
    # échoue avec ConfigEntryNotReady ou une autre exception.
    entry.async_on_unload(coordinator.async_shutdown)

    # Premier chargement des données.
    await coordinator.async_config_entry_first_refresh()

    # Recharge automatiquement l'intégration lorsque les options
    # de la ConfigEntry sont modifiées.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Les plateformes ne sont créées qu'après le premier refresh réussi.
    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> bool:
    """Décharge les plateformes de l'intégration."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )


async def async_remove_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> None:
    """Supprime les données runtime globales associées à la ConfigEntry."""
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
    entry: HAMonitoringConfigEntry,
) -> None:
    """Recharge l'intégration."""
    await hass.config_entries.async_reload(entry.entry_id)
