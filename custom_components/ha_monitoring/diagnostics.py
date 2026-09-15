"""Support du diagnostic pour l'intégration HA Monitoring."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)

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
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
) -> dict[str, Any]:
    """Retourne les données de diagnostic pour une ConfigEntry donnée."""
    coordinator: HAMonitoringCoordinator = entry.runtime_data

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(
                dict(entry.data),
                TO_REDACT,
            ),
            "options": async_redact_data(
                dict(entry.options),
                TO_REDACT,
            ),
        },
        "coordinator": {
            "is_ready": coordinator._is_ready,
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception)
                if coordinator.last_exception
                else None
            ),
            "maintenance_mode": coordinator.maintenance_mode,
            "scan_status": {
                "last_scan_timestamp": (
                    coordinator.last_scan_timestamp.isoformat()
                    if coordinator.last_scan_timestamp is not None
                    else None
                ),
                "last_scan_duration": coordinator.last_scan_duration,
                "last_traces_scan_timestamp": (
                    coordinator.last_traces_scan_timestamp.isoformat()
                    if coordinator.last_traces_scan_timestamp is not None
                    else None
                ),
                "last_traces_scan_duration": (
                    coordinator.last_traces_scan_duration
                ),
                "last_system_info_scan_timestamp": (
                    coordinator.last_system_info_scan_timestamp.isoformat()
                    if coordinator.last_system_info_scan_timestamp is not None
                    else None
                ),
                "last_system_info_scan_duration": (
                    coordinator.last_system_info_scan_duration
                ),
                "last_backup_scan_timestamp": (
                    coordinator.last_backup_scan_timestamp.isoformat()
                    if coordinator.last_backup_scan_timestamp is not None
                    else None
                ),
                "last_backup_scan_duration": (
                    coordinator.last_backup_scan_duration
                ),
            },
            "data": (
                async_redact_data(
                    dict(coordinator.data),
                    TO_REDACT,
                )
                if coordinator.data
                else {}
            ),
        },
    }
