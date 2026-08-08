"""Support du diagnostic pour l'intégration HA Monitoring."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HAMonitoringCoordinator

# Liste élargie des clés sensibles à anonymiser dans les rapports de diagnostic
TO_REDACT: set[str] = {
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
    "api_key",
    "email",
    "username",
    "serial",
    "device_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Retourne les données de diagnostic pour une ConfigEntry donnée."""
    coordinator: HAMonitoringCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception)
                if coordinator.last_exception
                else None
            ),
            "data": (
                async_redact_data(coordinator.data, TO_REDACT)
                if coordinator.data
                else {}
            ),
        },
    }