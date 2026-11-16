"""Tests for entity ID naming checks."""

from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.helpers.entity_registry import EntityNamePart

from custom_components.ha_monitoring.helpers.entity_naming import (
    get_entity_id_format,
    get_entity_naming_issues,
)


def _entry(
    entity_id: str,
    expected_entity_id: str,
    *,
    disabled: bool = False,
    name: str | None = None,
) -> SimpleNamespace:
    """Build a minimal registry entry double."""
    return SimpleNamespace(
        entity_id=entity_id,
        expected_entity_id=expected_entity_id,
        domain=entity_id.split(".", 1)[0],
        disabled=disabled,
        name=name,
    )


def test_entity_naming_uses_native_generator_and_skips_disabled() -> None:
    """Only enabled registry entries are checked using the HA generator."""
    first = _entry("sensor.old_name", "sensor.area_temperature")
    disabled = _entry("sensor.disabled", "sensor.expected", disabled=True)
    registry = Mock()
    registry.entities = {
        first.entity_id: first,
        disabled.entity_id: disabled,
    }
    registry.async_regenerate_entity_id.side_effect = lambda entry, *, reserved_entity_ids: (
        entry.expected_entity_id
    )
    hass = Mock()
    hass.states.get.return_value = None

    issues, checked = get_entity_naming_issues(
        hass,
        registry,
        excluded_entities=[],
        excluded_domains=[],
        excluded_globs=[],
    )

    assert issues == [
        {
            "entity_id": "sensor.old_name",
            "expected_entity_id": "sensor.area_temperature",
        }
    ]
    assert checked == 1
    registry.async_regenerate_entity_id.assert_called_once_with(
        first,
        reserved_entity_ids={"sensor.area_temperature"},
    )


def test_entity_naming_applies_entity_domain_and_glob_exclusions() -> None:
    """Configured entity, domain and wildcard exclusions are applied."""
    entries = [
        _entry("sensor.explicit", "sensor.expected"),
        _entry("automation.ignored", "automation.expected"),
        _entry("sensor.room_temperature", "sensor.expected_temperature"),
        _entry("sensor.checked", "sensor.expected_checked"),
    ]
    registry = Mock()
    registry.entities = {entry.entity_id: entry for entry in entries}
    registry.async_regenerate_entity_id.side_effect = lambda entry, *, reserved_entity_ids: (
        entry.expected_entity_id
    )
    hass = Mock()
    hass.states.get.return_value = None

    issues, checked = get_entity_naming_issues(
        hass,
        registry,
        excluded_entities=["sensor.explicit"],
        excluded_domains=["automation"],
        excluded_globs=["sensor.room_*"],
    )

    assert checked == 1
    assert issues == [
        {
            "entity_id": "sensor.checked",
            "expected_entity_id": "sensor.expected_checked",
        }
    ]


def test_entity_id_format_uses_home_assistant_default() -> None:
    """The default format matches Home Assistant's built-in ordering."""
    registry = SimpleNamespace(settings=SimpleNamespace(entity_id_parts=None))

    assert get_entity_id_format(registry) == "area > parent_device > device > entity"


def test_entity_id_format_uses_configured_order() -> None:
    """The format attribute reflects the configured HA setting and its order."""
    registry = SimpleNamespace(
        settings=SimpleNamespace(
            entity_id_parts=(
                EntityNamePart.FLOOR,
                EntityNamePart.AREA,
                EntityNamePart.DEVICE,
                EntityNamePart.ENTITY,
            )
        )
    )

    assert get_entity_id_format(registry) == "floor > area > device > entity"
