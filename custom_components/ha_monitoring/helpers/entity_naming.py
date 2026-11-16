"""Helpers for checking entity IDs against Home Assistant's current naming rules."""

from collections.abc import Sequence
from fnmatch import fnmatch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from ..types import EntityNamingData


def get_entity_naming_issues(
    hass: HomeAssistant,
    registry: EntityRegistry,
    *,
    excluded_entities: Sequence[str],
    excluded_domains: Sequence[str],
    excluded_globs: Sequence[str],
) -> tuple[list[EntityNamingData], int]:
    """Return enabled registry entries whose IDs differ from HA's generated IDs.

    Home Assistant's registry generator is the source of truth. The reserved set
    mirrors the ordering used by the entity registry UI when generating several IDs.
    """
    excluded_entity_ids = set(excluded_entities)
    excluded_domain_names = set(excluded_domains)
    excluded_patterns = tuple(
        pattern.lower().strip() for pattern in excluded_globs if pattern.strip()
    )

    reserved_entity_ids: set[str] = set()
    issues: list[EntityNamingData] = []
    checked = 0

    for entry in sorted(registry.entities.values(), key=lambda item: item.entity_id):
        if entry.disabled:
            continue

        if entry.entity_id in excluded_entity_ids or entry.domain in excluded_domain_names:
            continue

        state = hass.states.get(entry.entity_id)
        friendly_name = str(state.attributes.get("friendly_name", "")) if state is not None else ""
        names_to_check = (
            entry.entity_id.lower(),
            friendly_name.lower(),
            (entry.name or "").lower(),
        )

        if any(
            fnmatch(value, pattern) for value in names_to_check for pattern in excluded_patterns
        ):
            continue

        checked += 1
        expected_entity_id = registry.async_regenerate_entity_id(
            entry,
            reserved_entity_ids=reserved_entity_ids,
        )
        reserved_entity_ids.add(expected_entity_id)

        if entry.entity_id != expected_entity_id:
            issues.append(
                {
                    "entity_id": entry.entity_id,
                    "expected_entity_id": expected_entity_id,
                }
            )

    return issues, checked
