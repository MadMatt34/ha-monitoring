"""System monitoring helpers."""

from datetime import datetime, timedelta
from fnmatch import fnmatch
import logging

from homeassistant.components.hassio import (
    HassioNotReadyError,
    get_addons_info,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
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


def _extract_last_seen_dt(
    state_obj: State,
    last_seen_suffixes: tuple[str, ...],
) -> datetime | None:
    """Extract the last-seen datetime from a state."""
    dt_value = dt_util.parse_datetime(state_obj.state)

    if dt_value is not None:
        return dt_util.as_utc(dt_value)

    for attribute_name in last_seen_suffixes:
        value = state_obj.attributes.get(attribute_name)

        if isinstance(value, datetime):
            return dt_util.as_utc(value)

        if isinstance(value, str):
            dt_value = dt_util.parse_datetime(value)

            if dt_value is not None:
                return dt_util.as_utc(dt_value)

        if isinstance(value, (int, float)):
            try:
                return dt_util.utc_from_timestamp(float(value))
            except (OverflowError, OSError, ValueError):
                continue

    return None


def scan_all_states(
    hass: HomeAssistant,
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
    """Scan all Home Assistant states in a single pass."""
    now = dt_util.utcnow()
    cutoff = now - timedelta(hours=float(timeout_hours))

    excluded_updates_set = set(excluded_updates)
    excluded_unavailable_entities_set = set(excluded_unavailable_entities)
    excluded_unavailable_domains_set = set(excluded_unavailable_domains)
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

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    def is_excluded_by_glob(text: str) -> bool:
        """Return whether text matches an unavailable exclusion glob."""
        if not text:
            return False

        text_lower = text.lower()

        return any(
            fnmatch(text_lower, pattern)
            for pattern in excluded_unavailable_globs_normalized
        )

    for state_obj in hass.states.async_all():
        entity_id = state_obj.entity_id
        domain = state_obj.domain

        friendly_name = state_obj.attributes.get("friendly_name") or entity_id

        entity_entry = entity_registry.async_get(entity_id)

        # Never monitor entities created by this integration.
        if entity_entry and entity_entry.platform == DOMAIN:
            continue

        # Unavailable / unknown entities.
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
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
                        "state": state_obj.state,
                    }
                )

            continue

        # Updates available.
        if domain == "update" and state_obj.state == "on":
            if entity_id not in excluded_updates_set:
                updates.append(
                    {
                        "entity_id": entity_id,
                        "name": friendly_name,
                        "installed_version": (
                            state_obj.attributes.get("installed_version")
                            or "Inconnue"
                        ),
                        "latest_version": (
                            state_obj.attributes.get("latest_version")
                            or "Inconnue"
                        ),
                    }
                )

            continue

        # Offline device detection based on last_seen entities.
        if not entity_id.endswith(last_seen_suffixes):
            continue

        device_id = entity_entry.device_id if entity_entry else None

        if (
            device_id is not None
            and device_id in excluded_offline_set
        ) or entity_id in excluded_offline_set:
            continue

        device_name: str | None = None
        platform = "inconnu"

        if entity_entry:
            platform = entity_entry.platform or "inconnu"

            if device_id:
                device_entry = device_registry.async_get(device_id)

                if device_entry:
                    device_name = (
                        device_entry.name_by_user
                        or device_entry.name
                    )

        display_name = device_name or friendly_name

        if display_name in excluded_offline_set:
            continue

        if display_name in offline_devices:
            continue

        last_seen_dt = _extract_last_seen_dt(
            state_obj,
            last_seen_suffixes,
        )

        if last_seen_dt is None or last_seen_dt >= cutoff:
            continue

        offline_devices.add(display_name)

        offline.append(
            {
                "device": display_name,
                "date": format_date_local(last_seen_dt) or "",
                "platform": platform,
            }
        )

    return updates, unavailable, offline


async def async_get_addons(
    hass: HomeAssistant,
    excluded: list[str],
) -> list[str]:
    """Return watchdog-enabled auto-start add-ons that are not started."""
    try:
        addons_info = get_addons_info(hass)
    except HassioNotReadyError:
        return []

    excluded_set = set(excluded)
    failed: list[str] = []

    for slug, addon in addons_info.items():
        if addon is None:
            continue

        if (
            addon.get("watchdog") is True
            and addon.get("boot") == "auto"
            and addon.get("state") != "started"
        ):
            name = str(addon.get("name") or slug)

            if name not in excluded_set and slug not in excluded_set:
                failed.append(name)

    return failed


async def async_get_failed_integrations(
    hass: HomeAssistant,
    excluded: list[str],
) -> list[FailedIntegrationData]:
    """Return failed config entries with native Home Assistant translations."""
    error_states = {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
    }

    excluded_set = set(excluded)

    entries = [
        entry
        for entry in hass.config_entries.async_entries()
        if (
            entry.state in error_states
            and entry.domain not in excluded_set
            and entry.title not in excluded_set
            and entry.entry_id not in excluded_set
        )
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

    failed_entries: list[FailedIntegrationData] = []

    for entry in entries:
        title_key = f"component.{entry.domain}.title"

        integration_name = integration_titles.get(
            title_key,
            entry.domain,
        )

        friendly_reason: str | None = None

        translation_key = entry.error_reason_translation_key

        if translation_key:
            error_key = (
                f"component.{entry.domain}.config.error."
                f"{translation_key}"
            )
            abort_key = (
                f"component.{entry.domain}.config.abort."
                f"{translation_key}"
            )

            friendly_reason = (
                config_translations.get(error_key)
                or config_translations.get(abort_key)
            )

        if friendly_reason is not None:
            placeholders = (
                entry.error_reason_translation_placeholders or {}
            )

            try:
                friendly_reason = friendly_reason.format(
                    **placeholders
                )
            except (KeyError, IndexError):
                _LOGGER.debug(
                    "Translation placeholders missing for "
                    "%s config entry %s",
                    entry.domain,
                    entry.entry_id,
                )

        if friendly_reason is None:
            state_issue_key = {
                ConfigEntryState.SETUP_RETRY: (
                    f"component.{DOMAIN}.issues.setup_retry.title"
                ),
                ConfigEntryState.SETUP_ERROR: (
                    f"component.{DOMAIN}.issues.setup_error.title"
                ),
                ConfigEntryState.MIGRATION_ERROR: (
                    f"component.{DOMAIN}.issues.migration_error.title"
                ),
            }.get(entry.state)

            if state_issue_key:
                friendly_reason = issue_translations.get(
                    state_issue_key
                )

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
    """Return active repairs from the native Home Assistant issue registry."""
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

    excluded_set = set(excluded)
    pending: list[PendingRepairData] = []

    for issue in active_issues:
        issue_identifier = f"{issue.domain}: {issue.issue_id}"

        if (
            issue_identifier in excluded_set
            or issue.domain in excluded_set
            or issue.issue_id in excluded_set
        ):
            continue

        friendly_name: str | None = None

        if issue.translation_key:
            translation_id = (
                f"component.{issue.domain}.issues."
                f"{issue.translation_key}.title"
            )

            raw_title = translations.get(translation_id)

            if raw_title is not None:
                placeholders = issue.translation_placeholders or {}

                try:
                    friendly_name = raw_title.format(
                        **placeholders
                    )
                except (KeyError, IndexError):
                    _LOGGER.debug(
                        "Translation placeholders missing for "
                        "repair %s:%s",
                        issue.domain,
                        issue.issue_id,
                    )

        if friendly_name is None:
            friendly_name = issue.issue_id

        pending.append(
            {
                "name": friendly_name,
                "domain": issue.domain,
                "date": format_date_local(issue.created) or "",
                "issue_id": issue.issue_id,
            }
        )

    return pending
