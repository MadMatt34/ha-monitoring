"""Tests for entity ID naming checks."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant.helpers.entity_registry import EntityNamePart

from custom_components.ha_monitoring.helpers.id_naming import (
    get_entity_id_format,
    get_id_naming_issues,
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
        area_id=None,
    )


def _get_id_naming_issues(*args: object, **kwargs: object) -> tuple[list[dict[str, str | None]], int, int]:
    """Run the helper with a test double for HA's effective-area resolver."""
    with patch(
        "custom_components.ha_monitoring.helpers.id_naming.er.async_get_effective_area_id",
        side_effect=lambda hass, entry: entry.area_id,
    ):
        return get_id_naming_issues(*args, **kwargs)  # type: ignore[arg-type]


def test_id_naming_uses_native_generator_and_skips_disabled() -> None:
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

    issues, checked, total = _get_id_naming_issues(
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
            "area": None,
        }
    ]
    assert checked == 1
    assert total == 1
    hass.states.get.assert_not_called()
    registry.async_regenerate_entity_id.assert_called_once_with(
        first,
        reserved_entity_ids={"sensor.area_temperature"},
    )


def test_id_naming_includes_area_name() -> None:
    """The issue entry includes the assigned area's display name."""
    entry = _entry("sensor.old_name", "sensor.area_temperature")
    entry.area_id = "living_room"
    registry = Mock()
    registry.entities = {entry.entity_id: entry}
    registry.async_regenerate_entity_id.return_value = "sensor.area_temperature"
    hass = Mock()
    hass.states.get.return_value = None
    area_registry = Mock()
    area_registry.async_get_area.return_value = SimpleNamespace(name="Living Room")

    with patch(
        "custom_components.ha_monitoring.helpers.id_naming.ar.async_get",
        return_value=area_registry,
    ):
        issues, checked, total = _get_id_naming_issues(
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
            "area": "Living Room",
        }
    ]
    assert checked == 1
    assert total == 1
    area_registry.async_get_area.assert_called_once_with("living_room")


def test_id_naming_applies_entity_domain_and_glob_exclusions() -> None:
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

    issues, checked, total = _get_id_naming_issues(
        hass,
        registry,
        excluded_entities=["sensor.explicit"],
        excluded_domains=["automation"],
        excluded_globs=["sensor.room_*"],
    )

    assert checked == 1
    assert total == 1
    assert issues == [
        {
            "entity_id": "sensor.checked",
            "expected_entity_id": "sensor.expected_checked",
            "area": None,
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
                EntityNamePart.PARENT_DEVICE,
                EntityNamePart.DEVICE,
                EntityNamePart.ENTITY,
            )
        )
    )

    assert get_entity_id_format(registry) == "floor > area > parent_device > device > entity"


def test_id_naming_limits_list_but_counts_all_issues() -> None:
    """Only the first 100 issues are retained while the total stays accurate."""
    entries = [_entry(f"sensor.old_{index:03}", f"sensor.new_{index:03}") for index in range(105)]
    registry = Mock()
    registry.entities = {entry.entity_id: entry for entry in entries}
    registry.async_regenerate_entity_id.side_effect = lambda entry, *, reserved_entity_ids: (
        entry.expected_entity_id
    )
    hass = Mock()
    hass.states.get.return_value = None

    issues, checked, total = _get_id_naming_issues(
        hass,
        registry,
        excluded_entities=[],
        excluded_domains=[],
        excluded_globs=[],
    )

    assert checked == 105
    assert total == 105
    assert len(issues) == 100


def test_id_naming_checks_friendly_name_only_when_globs_are_configured() -> None:
    """Friendly names are fetched only when glob exclusions need them."""
    entry = _entry("sensor.old_name", "sensor.expected")
    registry = Mock()
    registry.entities = {entry.entity_id: entry}
    registry.async_regenerate_entity_id.return_value = "sensor.expected"
    hass = Mock()
    hass.states.get.return_value = SimpleNamespace(
        attributes={"friendly_name": "Living Room Temperature"}
    )

    issues, checked, total = _get_id_naming_issues(
        hass,
        registry,
        excluded_entities=[],
        excluded_domains=[],
        excluded_globs=["living room*"],
    )

    assert issues == []
    assert checked == 0
    assert total == 0
    hass.states.get.assert_called_once_with("sensor.old_name")
    registry.async_regenerate_entity_id.assert_not_called()


def test_id_naming_resolves_each_area_name_only_once() -> None:
    """Repeated issues in one area reuse its already resolved display name."""
    entries = [
        _entry("sensor.first", "sensor.expected_first"),
        _entry("sensor.second", "sensor.expected_second"),
    ]
    for entry in entries:
        entry.area_id = "living_room"

    registry = Mock()
    registry.entities = {entry.entity_id: entry for entry in entries}
    registry.async_regenerate_entity_id.side_effect = lambda entry, *, reserved_entity_ids: (
        entry.expected_entity_id
    )
    hass = Mock()
    hass.states.get.return_value = None
    area_registry = Mock()
    area_registry.async_get_area.return_value = SimpleNamespace(name="Living Room")

    with patch(
        "custom_components.ha_monitoring.helpers.id_naming.ar.async_get",
        return_value=area_registry,
    ) as get_area_registry:
        issues, checked, total = _get_id_naming_issues(
            hass,
            registry,
            excluded_entities=[],
            excluded_domains=[],
            excluded_globs=[],
        )

    assert checked == 2
    assert total == 2
    assert [issue["area"] for issue in issues] == ["Living Room", "Living Room"]
    get_area_registry.assert_called_once_with(hass)
    area_registry.async_get_area.assert_called_once_with("living_room")


def test_id_naming_uses_effective_area_inherited_from_device() -> None:
    """An area inherited from a device is included even without entity.area_id."""
    entry = _entry("sensor.old_name", "sensor.area_temperature")
    registry = Mock()
    registry.entities = {entry.entity_id: entry}
    registry.async_regenerate_entity_id.return_value = "sensor.area_temperature"
    hass = Mock()
    area_registry = Mock()
    area_registry.async_get_area.return_value = SimpleNamespace(name="Living Room")

    with (
        patch(
            "custom_components.ha_monitoring.helpers.id_naming.er.async_get_effective_area_id",
            return_value="living_room",
        ) as get_effective_area,
        patch(
            "custom_components.ha_monitoring.helpers.id_naming.ar.async_get",
            return_value=area_registry,
        ),
    ):
        issues, checked, total = get_id_naming_issues(
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
            "area": "Living Room",
        }
    ]
    assert checked == 1
    assert total == 1
    get_effective_area.assert_called_once_with(hass, entry)
    area_registry.async_get_area.assert_called_once_with("living_room")
