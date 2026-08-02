"""Diagnostics support for HA Monitoring."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Liste des clés à anonymiser dans le fichier JSON généré.
# Tu peux ajouter ici d'autres clés si ton intégration manipule des données sensibles.
TO_REDACT = {
    "title",
    "unique_id",
    "mac",
    "ip",
    "password",
    "token",
    "secret",
    "lat",
    "latitude",
    "lon",
    "longitude",
    "host",
    "port",
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # On récupère le coordinator depuis les données stockées lors de l'initialisation
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Construction de l'objet JSON de diagnostic
    diagnostics_data = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": async_redact_data(entry.title, TO_REDACT),
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "data": async_redact_data(coordinator.data, TO_REDACT) if coordinator.data else {},
        },
    }

    return diagnostics_data
