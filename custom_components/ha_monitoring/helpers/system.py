"""Collecteurs système : états, hors-ligne, extensions, intégrations et réparations."""

from datetime import datetime, timedelta
import logging
from typing import Any

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
from .utils import format_date_local, is_hassio_running

_LOGGER = logging.getLogger("custom_components.ha_monitoring.system")


def _extract_last_seen_dt(state_obj: Any, last_seen_suffixes: tuple[str, ...]) -> datetime | None:
    """Extrait et convertit en datetime UTC la date de dernière vue d'une entité."""
    dt_val = dt_util.parse_datetime(str(state_obj.state))
    if dt_val:
        return dt_util.as_utc(dt_val)

    attrs = state_obj.attributes or {}
    for attr_key in last_seen_suffixes:
        val = attrs.get(attr_key)
        if val is None:
            continue

        if isinstance(val, (int, float)):
            try:
                ts = val / 1000.0 if val > 1e11 else float(val)
                return datetime.fromtimestamp(ts, tz=dt_util.UTC)
            except (ValueError, OverflowError, OSError):
                pass
        elif isinstance(val, str):
            dt_val = dt_util.parse_datetime(val)
            if dt_val:
                return dt_util.as_utc(dt_val)
        elif isinstance(val, datetime):
            return dt_util.as_utc(val)

    return None


def scan_all_states(
    hass: HomeAssistant,
    excluded_updates: list[str],
    excluded_unavailable_entities: list[str],
    excluded_unavailable_domains: list[str],
    excluded_offline: list[str],
    timeout_hours: float,
    last_seen_suffixes: tuple[str, ...] = DEFAULT_LAST_SEEN_SUFFIX,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parcourt TOUS les états de Home Assistant en une seule passe."""
    now = dt_util.utcnow()
    cutoff = now - timedelta(hours=float(timeout_hours))

    excl_updates = set(excluded_updates)
    excl_unavail_entities = set(excluded_unavailable_entities)
    excl_unavail_domains = set(excluded_unavailable_domains)
    excl_offline = set(excluded_offline)

    updates, unavailable, offline = [], [], []

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for state_obj in hass.states.async_all():
        entity_id = state_obj.entity_id
        domain = state_obj.domain
        friendly_name = state_obj.attributes.get("friendly_name") or entity_id

        entity_entry = ent_reg.async_get(entity_id)
        if entity_entry and entity_entry.platform == DOMAIN:
            continue

        # 1. Entités indisponibles ou inconnues
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if entity_id not in excl_unavail_entities and domain not in excl_unavail_domains:
                unavailable.append({
                    "entity_id": entity_id,
                    "name": friendly_name,
                    "domain": domain,
                    "state": state_obj.state,
                })
            continue

        # 2. Mises à jour disponibles
        if domain == "update" and state_obj.state == "on":
            if entity_id not in excl_updates:
                updates.append({
                    "entity_id": entity_id,
                    "name": friendly_name,
                    "installed_version": state_obj.attributes.get("installed_version") or "Inconnue",
                    "latest_version": state_obj.attributes.get("latest_version") or "Inconnue",
                })
            continue

        # 3. Détection hors-ligne (last_seen)
        if entity_id.endswith(last_seen_suffixes):
            device_id = entity_entry.device_id if entity_entry else None
            if (device_id and device_id in excl_offline) or entity_id in excl_offline:
                continue

            device_name = None
            platform = "inconnu"

            if entity_entry:
                platform = entity_entry.platform or "inconnu"
                if device_id:
                    device_entry = dev_reg.async_get(device_id)
                    if device_entry:
                        device_name = device_entry.name_by_user or device_entry.name

            display_name = device_name or friendly_name
            if display_name in excl_offline:
                continue

            last_seen_dt = _extract_last_seen_dt(state_obj, last_seen_suffixes)

            if last_seen_dt and last_seen_dt < cutoff:
                if not any(item["device"] == display_name for item in offline):
                    offline.append({
                        "device": display_name,
                        "date": format_date_local(last_seen_dt),
                        "platform": platform,
                    })

    return updates, unavailable, offline


async def async_get_addons(hass: HomeAssistant, excluded: list[str]) -> list[str]:
    """Récupère les modules complémentaires (Add-ons) arrêtés ou en erreur."""
    if not is_hassio_running(hass):
        return []

    client = hass.data.get("hassio")
    if not client:
        return []

    try:
        if hasattr(client, "async_get_addons_info"):
            addons_info = await client.async_get_addons_info()
        elif hasattr(client, "get_addons_info"):
            addons_info = await client.get_addons_info()
        else:
            return []

        addons = addons_info.get("addons", [])
        excl_set = set(excluded)

        failed = []
        for addon in addons:
            name = addon.get("name", "")
            slug = addon.get("slug", "")
            if name in excl_set or slug in excl_set:
                continue

            is_auto = addon.get("watchdog", False) or addon.get("boot") == "auto"
            if is_auto and addon.get("state") in ("stopped", "unknown"):
                failed.append(name or slug)

        return failed
    except Exception as err:
        _LOGGER.error("Erreur lors de la récupération des Add-ons : %s", err)
        return []


async def async_get_failed_integrations(hass: HomeAssistant, excluded: list[str]) -> list[dict[str, Any]]:
    """Récupère les intégrations en erreur avec traductions officielles."""
    error_states = {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
    }
    excl_set = set(excluded)

    entries = [
        entry for entry in hass.config_entries.async_entries()
        if entry.state in error_states
        and entry.domain not in excl_set
        and entry.title not in excl_set
        and entry.entry_id not in excl_set
    ]

    if not entries:
        return []

    domains = {entry.domain for entry in entries}
    lang = hass.config.language

    async def _safe_get_translations(category: str, req_domains: set[str]) -> dict[str, str]:
        try:
            return await async_get_translations(hass, lang, category, domains=req_domains)
        except Exception:
            return {}

    integration_titles = await _safe_get_translations("title", domains)
    config_translations = await _safe_get_translations("config", domains)
    issue_translations = await _safe_get_translations("issues", domains | {DOMAIN})

    failed_entries = []

    for entry in entries:
        title_key = f"component.{entry.domain}.title"
        integration_name = integration_titles.get(title_key) or entry.domain.replace("_", " ").title()

        raw_reason = getattr(entry, "reason", None)
        friendly_reason = None

        if raw_reason:
            error_key = f"component.{entry.domain}.config.error.{raw_reason}"
            abort_key = f"component.{entry.domain}.config.abort.{raw_reason}"
            issue_key = f"component.{entry.domain}.issues.{raw_reason}.title"

            friendly_reason = (
                config_translations.get(error_key)
                or config_translations.get(abort_key)
                or issue_translations.get(issue_key)
            )

        if not friendly_reason:
            if entry.state == ConfigEntryState.SETUP_RETRY:
                friendly_reason = issue_translations.get(f"component.{DOMAIN}.issues.setup_retry.title")
            elif entry.state == ConfigEntryState.SETUP_ERROR:
                friendly_reason = issue_translations.get(f"component.{DOMAIN}.issues.setup_error.title")
            elif entry.state == ConfigEntryState.MIGRATION_ERROR:
                friendly_reason = issue_translations.get(f"component.{DOMAIN}.issues.migration_error.title")

        friendly_reason = friendly_reason or raw_reason or entry.state.value

        failed_entries.append({
            "name": integration_name,
            "entry_name": entry.title,
            "domain": entry.domain,
            "entry_id": entry.entry_id,
            "state": entry.state.value,
            "reason": friendly_reason,
        })

    return failed_entries


async def async_get_pending_repairs(hass: HomeAssistant, excluded: list[str]) -> list[dict[str, Any]]:
    """Récupère les réparations (issues) en attente."""
    issue_registry = ir.async_get(hass)
    active_issues = [
        issue for issue in issue_registry.issues.values()
        if getattr(issue, "active", True) and getattr(issue, "dismissed_version", None) is None
    ]

    domains = {issue.domain for issue in active_issues}
    translations = {}
    if domains:
        try:
            translations = await async_get_translations(hass, hass.config.language, "issues", domains=domains)
        except Exception:
            translations = {}

    excl_set = set(excluded)
    pending = []

    for issue in active_issues:
        issue_identifier = f"{issue.domain}: {issue.issue_id}"
        if issue_identifier in excl_set or issue.domain in excl_set or issue.issue_id in excl_set:
            continue

        key_name = getattr(issue, "translation_key", None) or issue.issue_id
        trans_key = f"component.{issue.domain}.issues.{key_name}.title"

        friendly_name = None
        if trans_key in translations:
            raw_title = translations[trans_key]
            placeholders = getattr(issue, "translation_placeholders", None)
            if isinstance(placeholders, dict):
                try:
                    friendly_name = raw_title.format(**placeholders)
                except Exception:
                    friendly_name = raw_title
            else:
                friendly_name = raw_title

        if not friendly_name:
            domain_friendly = issue.domain.replace("_", " ").title()
            issue_friendly = key_name.replace("_", " ").capitalize()
            friendly_name = f"{domain_friendly} — {issue_friendly}"

        repair_item = {
            "name": friendly_name,
            "domain": issue.domain,
            "date": format_date_local(getattr(issue, "created", None)),
            "issue_id": issue.issue_id,
        }

        if repair_item not in pending:
            pending.append(repair_item)

    return pending