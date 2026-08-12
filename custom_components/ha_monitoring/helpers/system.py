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


def _optional_str(value: object) -> str | None:
    """Retourne une valeur sous forme de chaîne si elle est textuelle."""
    return value if isinstance(value, str) else None


def _matches_exclusions(
    value: str,
    exclusions: set[str],
) -> bool:
    """Retourne si une valeur correspond à une exclusion glob."""
    value_lower = value.lower()

    return any(
        fnmatch(
            value_lower,
            pattern.lower(),
        )
        for pattern in exclusions
    )


def _snapshot_states(
    hass: HomeAssistant,
    last_seen_suffixes: tuple[str, ...],
) -> list[StateScanData]:
    """Capture les données HA nécessaires au scan."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    monitoring_entity_ids = {
        entry.entity_id for entry in entity_registry.entities.values() if entry.platform == DOMAIN
    }

    snapshot: list[StateScanData] = []

    for state_obj in hass.states.async_all():
        entity_id = state_obj.entity_id
        attributes = state_obj.attributes

        friendly_name = _optional_str(attributes.get("friendly_name")) or entity_id

        is_last_seen = (
            state_obj.domain == "sensor"
            and attributes.get("device_class") == "timestamp"
            and entity_id.endswith(last_seen_suffixes)
        )

        device_id: str | None = None
        device_name: str | None = None
        platform = "inconnu"

        if is_last_seen:
            entity_entry = entity_registry.async_get(entity_id)

            if entity_entry is not None:
                device_id = entity_entry.device_id
                platform = entity_entry.platform or "inconnu"

                if device_id is not None:
                    device_entry = device_registry.async_get(device_id)

                    if device_entry is not None:
                        device_name = device_entry.name_by_user or device_entry.name

        snapshot.append(
            {
                "entity_id": entity_id,
                "domain": state_obj.domain,
                "state": state_obj.state,
                "friendly_name": friendly_name,
                "installed_version": _optional_str(attributes.get("installed_version")),
                "latest_version": _optional_str(attributes.get("latest_version")),
                "device_id": device_id,
                "device_name": device_name,
                "platform": (DOMAIN if entity_id in monitoring_entity_ids else platform),
            }
        )

    return snapshot


def _extract_last_seen_dt(
    state_data: StateScanData,
) -> datetime | None:
    """Extrait la date de dernière vue depuis l'état ISO du sensor."""
    parsed = dt_util.parse_datetime(state_data["state"])

    if parsed is None:
        return None

    return dt_util.as_utc(parsed)


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
    excluded_unavailable_entities_set = set(excluded_unavailable_entities)
    excluded_unavailable_domains_set = set(excluded_unavailable_domains)
    excluded_offline_set = set(excluded_offline)

    excluded_unavailable_globs_normalized = {
        pattern.lower().strip() for pattern in (excluded_unavailable_globs or []) if pattern
    }

    updates: list[UpdateEntityData] = []
    unavailable: list[UnavailableEntityData] = []
    offline: list[OfflineDeviceData] = []
    offline_devices: set[str] = set()

    for state_data in states:
        entity_id = state_data["entity_id"]
        domain = state_data["domain"]
        state = state_data["state"]
        friendly_name = state_data["friendly_name"]

        if state_data["platform"] == DOMAIN:
            continue

        if state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if (
                entity_id not in excluded_unavailable_entities_set
                and domain not in excluded_unavailable_domains_set
                and not _matches_exclusions(
                    entity_id,
                    excluded_unavailable_globs_normalized,
                )
                and not _matches_exclusions(
                    friendly_name,
                    excluded_unavailable_globs_normalized,
                )
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

        if domain == "update" and state == "on":
            if entity_id not in excluded_updates_set:
                updates.append(
                    {
                        "entity_id": entity_id,
                        "name": friendly_name,
                        "installed_version": (state_data["installed_version"] or "Inconnue"),
                        "latest_version": (state_data["latest_version"] or "Inconnue"),
                    }
                )

            continue

        if not entity_id.endswith(last_seen_suffixes):
            continue

        device_id = state_data["device_id"]

        if (
            device_id is not None and device_id in excluded_offline_set
        ) or entity_id in excluded_offline_set:
            continue

        display_name = state_data["device_name"] or friendly_name

        if display_name in excluded_offline_set:
            continue

        if display_name in offline_devices:
            continue

        last_seen_dt = _extract_last_seen_dt(state_data)

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


async def async_get_addons(
    hass: HomeAssistant,
    excluded: list[str],
) -> list[str]:
    """Retourne les add-ons watchdog/auto-start non démarrés."""
    try:
        addons_info = get_addons_info(hass)
    except HassioNotReadyError:
        return []

    excluded_set = {value.strip() for value in excluded if value.strip()}

    failed: list[str] = []

    for slug, addon in addons_info.items():
        if addon is None:
            continue

        if (
            addon.get("watchdog") is not True
            or addon.get("boot") != "auto"
            or addon.get("state") == "started"
        ):
            continue

        name = str(addon.get("name") or slug)

        if _matches_exclusions(name, excluded_set) or _matches_exclusions(slug, excluded_set):
            continue

        failed.append(name)

    return failed


async def async_get_failed_integrations(
    hass: HomeAssistant,
    excluded: list[str],
) -> list[FailedIntegrationData]:
    """Retourne les ConfigEntries en erreur avec traduction native."""
    error_states = {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
    }

    entries = [
        entry for entry in hass.config_entries.async_entries() if entry.state in error_states
    ]

    if not entries:
        return []

    integrations = {entry.domain for entry in entries}

    integration_titles = await async_get_translations(
        hass,
        hass.config.language,
        "title",
        integrations=integrations,
    )

    config_translations = await async_get_translations(
        hass,
        hass.config.language,
        "config",
        integrations=integrations,
    )

    issue_translations = await async_get_translations(
        hass,
        hass.config.language,
        "issues",
        integrations=integrations | {DOMAIN},
    )

    excluded_set = {value.strip() for value in excluded if value.strip()}

    failed_entries: list[FailedIntegrationData] = []

    for entry in entries:
        title_key = f"component.{entry.domain}.title"

        integration_name = integration_titles.get(
            title_key,
            entry.domain,
        )

        if (
            _matches_exclusions(
                integration_name,
                excluded_set,
            )
            or _matches_exclusions(
                entry.title,
                excluded_set,
            )
            or _matches_exclusions(
                entry.domain,
                excluded_set,
            )
            or _matches_exclusions(
                entry.entry_id,
                excluded_set,
            )
        ):
            continue

        friendly_reason: str | None = None
        translation_key = entry.error_reason_translation_key

        if translation_key:
            error_key = f"component.{entry.domain}.config.error.{translation_key}"
            abort_key = f"component.{entry.domain}.config.abort.{translation_key}"

            friendly_reason = config_translations.get(error_key) or config_translations.get(
                abort_key
            )

        if friendly_reason is not None:
            placeholders = entry.error_reason_translation_placeholders or {}

            try:
                friendly_reason = friendly_reason.format(**placeholders)
            except (KeyError, IndexError):
                _LOGGER.debug(
                    "Translation placeholders missing for %s config entry %s",
                    entry.domain,
                    entry.entry_id,
                )

        if friendly_reason is None:
            state_issue_key = {
                ConfigEntryState.SETUP_RETRY: (f"component.{DOMAIN}.issues.setup_retry.title"),
                ConfigEntryState.SETUP_ERROR: (f"component.{DOMAIN}.issues.setup_error.title"),
                ConfigEntryState.MIGRATION_ERROR: (
                    f"component.{DOMAIN}.issues.migration_error.title"
                ),
            }.get(entry.state)

            if state_issue_key:
                friendly_reason = issue_translations.get(state_issue_key)

        if friendly_reason is None:
            friendly_reason = entry.reason or entry.state.value

        failed_entries.append(
            {
                "name": integration_name,
                "entry_name": entry.title,
                "domain": entry.domain,
                "entry_id": entry.entry_id,
                "state": entry.state.value,
                "reason": friendly_reason,
            }
        )

    return failed_entries


async def async_get_pending_repairs(
    hass: HomeAssistant,
    excluded: list[str],
) -> list[PendingRepairData]:
    """Retourne les réparations actives du registre natif."""
    issue_registry = ir.async_get(hass)

    active_issues = [
        issue
        for issue in issue_registry.issues.values()
        if issue.active and issue.dismissed_version is None
    ]

    if not active_issues:
        return []

    integrations = {issue.domain for issue in active_issues}

    translations = await async_get_translations(
        hass,
        hass.config.language,
        "issues",
        integrations=integrations,
    )

    excluded_set = {value.strip() for value in excluded if value.strip()}

    pending: list[PendingRepairData] = []

    for issue in active_issues:
        issue_identifier = f"{issue.domain}: {issue.issue_id}"

        friendly_name: str | None = None

        if issue.translation_key:
            translation_id = f"component.{issue.domain}.issues.{issue.translation_key}.title"

            raw_title = translations.get(translation_id)

            if raw_title is not None:
                placeholders = issue.translation_placeholders or {}

                try:
                    friendly_name = raw_title.format(**placeholders)
                except (KeyError, IndexError):
                    _LOGGER.debug(
                        "Translation placeholders missing for repair %s:%s",
                        issue.domain,
                        issue.issue_id,
                    )

        if friendly_name is None:
            friendly_name = issue.issue_id

        if (
            _matches_exclusions(
                friendly_name,
                excluded_set,
            )
            or _matches_exclusions(
                issue_identifier,
                excluded_set,
            )
            or _matches_exclusions(
                issue.domain,
                excluded_set,
            )
            or _matches_exclusions(
                issue.issue_id,
                excluded_set,
            )
        ):
            continue

        pending.append(
            {
                "name": friendly_name,
                "domain": issue.domain,
                "date": format_date_local(issue.created) or "",
                "issue_id": issue.issue_id,
            }
        )

    return pending
