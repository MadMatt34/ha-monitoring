"""Tests for common monitoring sensor attributes."""

from custom_components.ha_monitoring.const import MAX_SENSOR_LIST_ITEMS
from custom_components.ha_monitoring.sensor import _get_list_attributes


def test_sensor_list_is_limited_and_reports_truncation() -> None:
    """Lists are capped while the full total remains available."""
    items = [{"entity_id": f"sensor.test_{index}"} for index in range(MAX_SENSOR_LIST_ITEMS + 5)]

    visible, truncated = _get_list_attributes(
        items,
        len(items),
        maintenance=False,
    )

    assert len(visible) == MAX_SENSOR_LIST_ITEMS
    assert visible == items[:MAX_SENSOR_LIST_ITEMS]
    assert truncated is True


def test_sensor_list_is_not_truncated_at_limit() -> None:
    """A list at or below the limit is fully exposed."""
    items = [{"entity_id": f"sensor.test_{index}"} for index in range(MAX_SENSOR_LIST_ITEMS)]

    visible, truncated = _get_list_attributes(
        items,
        len(items),
        maintenance=False,
    )

    assert visible == items
    assert truncated is False


def test_sensor_list_is_empty_during_maintenance() -> None:
    """Maintenance hides list items and does not report truncation."""
    items = [{"entity_id": f"sensor.test_{index}"} for index in range(MAX_SENSOR_LIST_ITEMS + 5)]

    visible, truncated = _get_list_attributes(
        items,
        len(items),
        maintenance=True,
    )

    assert visible == []
    assert truncated is False
