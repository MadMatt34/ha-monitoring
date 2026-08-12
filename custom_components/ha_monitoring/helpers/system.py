"""System monitoring helpers."""

from datetime import datetime, timedelta
from fnmatch import fnmatch
import logging
from typing import TypedDict

from homeassistant.components.hassio import (
    HassioNotReadyError,
    get_addons_info,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from ..const import DEFAULT_LAST_SEEN_SUFFIX, DOMAIN
from ..types import (
    FailedIntegrationData,
    OfflineDeviceData,
    PendingRepairData,
    UnavailableEntityData,
    UpdateEntityData,
)
from .utils import format_date_local

_LOGGER = logging.getLogger(__name__)


class StateScanData(TypedDict):
    """Snapshot minimal d'un état HA nécessaire au scan."""

    entity_id: str
    domain: str
    state: str
    friendly_name: str
    installed_version: str | None
    latest_version: str | None
    device_id: str | None
    device_name: str | None
    platform: str
    last_seen_values: dict[str, object]


def _snapshot_states(
    hass: HomeAssistant,
    last_seen_suffixes: tuple[str, ...],
) -> list[StateScanData]:
    """Capture les informations HA nécessaires au scan."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    snapshot: list[StateScanData] = []

    for state_obj in hass.states.async_all():
        entity_id = state_obj.entity_id
        domain = state_obj.domain
        attributes = state_obj.attributes

        entity_entry = entity_registry.async_get(entity_id)

        device_id = entity_entry.device_id if entity_entry else None
        device_name: str | None = None

        if device_id is not None:
            device_entry = device_registry.async_get(device_id)

            if device_entry is not None:
                device_name = (
                    device_entry.name_by_user
                    or device_entry.name
                )

        last_seen_values: dict[str, object] = {}

        if entity_id.endswith(last_seen_suffixes):
            for suffix in last_seen_suffixes:
                if suffix in attributes:
                    last_seen_values[suffix] = attributes[suffix]

        snapshot.append(
            {
                "entity_id": entity_id,
                "domain": domain,
                "state": state_obj.state,
                "friendly_name": (
                    attributes.get("friendly_name")
                    or entity_id
                ),
                "installed_version": attributes.get(
                    "installed_version"
                ),
                "latest_version": attributes.get(
                    "latest_version"
                ),
                "device_id": device_id,
                "device_name": device_name,
                "platform": (
                    entity_entry.platform
                    if entity_entry and entity_entry.platform
                    else "inconnu"
                ),
                "last_seen_values": last_seen_values,
            }
        )

    return snapshot


def _extract_last_seen_dt(
    state_data: StateScanData,
    last_seen_suffixes: tuple[str, ...],
) -> datetime | None:
    """Extrait la date de dernière vue d'un snapshot."""
    dt_value = dt_util.parse_datetime(state_data["state"])

    if dt_value is not None:
        return dt_util.as_utc(dt_value)

    for attribute_name in last_seen_suffixes:
        value = state_data["last_seen_values"].get(attribute_name)

        if isinstance(value, datetime):
            return dt_util.as_utc(value)

        if isinstance(value, str):
            dt_value = dt_util.parse_datetime(value)

            if dt_value is not None:
                return dt_util.as_utc(dt_value)

        if isinstance(value, (int, float)):
            try:
                return dt_util.utc_from_timestamp(
                    float(value)
                )
            except (OverflowError, OSError, ValueError):
                continue

    return None


def scan_all_states(
    states: list[StateScanData],
    excluded_updates: list[str],
    excluded_unavailable_entities: list[str],
    excluded_unavailable_domains: list[str],
    excluded_offline: list[str],
    timeout_hours: float,
    last_seen_suffixes: tuple[str, ...] = DEFAULT_LAST_SEEN_SUFFIX,
    excluded_unavailable_globs: list[str] | None = None,
) -> tuple[
    list[UpdateEntityData],
    list[UnavailableEntityData],
    list[OfflineDeviceData],
]:
    """Traite un snapshot d'états HA en une seule passe."""
    now = dt_util.utcnow()
    cutoff = now - timedelta(hours=float(timeout_hours))

    excluded_updates_set = set(excluded_updates)
    excluded_unavailable_entities_set = set(
        excluded_unavailable_entities
    )
    excluded_unavailable_domains_set = set(
        excluded_unavailable_domains
    )
    excluded_offline_set = set(excluded_offline)

    excluded_unavailable_globs_normalized = [
        pattern.lower().strip()
        for pattern in (excluded_unavailable_globs or [])
        if pattern
    ]

    updates: list[UpdateEntityData] = []
    unavailable: list[UnavailableEntityData] = []
    offline: list[OfflineDeviceData] = []
    offline_devices: set[str] = set()

    def is_excluded_by_glob(text: str) -> bool:
        """Retourne si le texte correspond à un glob exclu."""
        if not text:
            return False

        text_lower = text.lower()

        return any(
            fnmatch(
                text_lower,
                pattern,
            )
            for pattern in excluded_unavailable_globs_normalized
        )

    for state_data in states:
        entity_id = state_data["entity_id"]
        domain = state_data["domain"]
        state = state_data["state"]
        friendly_name = state_data["friendly_name"]

        # Les entités de HA Monitoring sont exclues directement à partir
        # de la plateforme issue du registry.
        if state_data["platform"] == DOMAIN:
            continue

        # Entités indisponibles / inconnues.
        if state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if (
                entity_id not in excluded_unavailable_entities_set
                and domain not in excluded_unavailable_domains_set
                and not is_excluded_by_glob(entity_id)
                and not is_excluded_by_glob(friendly_name)
            ):
                unavailable.append(
                    {
                        "entity_id": entity_id,
                        "name": friendly_name,
                        "domain": domain,
                        "state": state,
                    }
                )

            continue

        # Updates disponibles.
        if domain == "update" and state == "on":
            if entity_id not in excluded_updates_set:
                updates.append(
                    {
                        "entity_id": entity_id,
                        "name": friendly_name,
                        "installed_version": (
                            state_data["installed_version"]
                            or "Inconnue"
                        ),
                        "latest_version": (
                            state_data["latest_version"]
                            or "Inconnue"
                        ),
                    }
                )

            continue

        # Détection offline via last_seen.
        if not entity_id.endswith(last_seen_suffixes):
            continue

        device_id = state_data["device_id"]

        if (
            device_id is not None
            and device_id in excluded_offline_set
        ) or entity_id in excluded_offline_set:
            continue

        display_name = (
            state_data["device_name"]
            or friendly_name
        )

        if display_name in excluded_offline_set:
            continue

        if display_name in offline_devices:
            continue

        last_seen_dt = _extract_last_seen_dt(
            state_data,
            last_seen_suffixes,
        )

        if last_seen_dt is None or last_seen_dt >= cutoff:
            continue

        offline_devices.add(display_name)

        offline.append(
            {
                "device": display_name,
                "date": format_date_local(last_seen_dt) or "",
                "platform": state_data["platform"],
            }
        )

    return updates, unavailable, offline
