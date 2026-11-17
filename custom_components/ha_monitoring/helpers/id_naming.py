"""Helpers for checking entity IDs against Home Assistant's current naming rules."""

from collections.abc import Sequence
from fnmatch import fnmatch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.entity_registry import EntityNamePart, EntityRegistry

from ..const import MAX_SENSOR_LIST_ITEMS
from ..types import IdNamingData

_DEFAULT_ENTITY_ID_PARTS = (
    EntityNamePart.AREA,
    EntityNamePart.PARENT_DEVICE,
    EntityNamePart.DEVICE,
    EntityNamePart.ENTITY,
)


def get_entity_id_format(registry: EntityRegistry) -> str:
    """Return the effective entity ID format configured in Home Assistant."""
    parts = registry.settings.entity_id_parts or _DEFAULT_ENTITY_ID_PARTS
    return " > ".join(part.value for part in parts)


def get_id_naming_issues(
    hass: HomeAssistant,
    registry: EntityRegistry,
    *,
    excluded_entities: Sequence[str],
    excluded_domains: Sequence[str],
    excluded_globs: Sequence[str],
) -> tuple[list[IdNamingData], int, int]:
    """Return enabled registry entries whose IDs differ from HA's generated IDs.

    Home Assistant's registry generator is the source of truth. The reserved set
    mirrors the ordering used by the entity registry UI when generating several IDs.
    """
    excluded_entity_ids = set(excluded_entities)
    excluded_domain_names = set(excluded_domains)
    excluded_patterns = tuple(
        pattern.lower().strip() for pattern in excluded_globs if pattern.strip()
    )

    area_registry = ar.async_get(hass)
    reserved_entity_ids: set[str] = set()
    issues: list[IdNamingData] = []
    total = 0
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
            total += 1
            if len(issues) < MAX_SENSOR_LIST_ITEMS:
                issues.append(
                    {
                        "entity_id": entry.entity_id,
                        "expected_entity_id": expected_entity_id,
                        "area": (
                            area.name
                            if entry.area_id
                            and (area := area_registry.async_get_area(entry.area_id))
                            else None
                        ),
                    }
                )

    return issues, checked, total
