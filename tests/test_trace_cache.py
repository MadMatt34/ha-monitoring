"""Tests for the bounded trace-error cache."""

from custom_components.ha_monitoring.const import MAX_SENSOR_LIST_ITEMS
from custom_components.ha_monitoring.coordinator import _limit_trace_error_cache


def _error(index: int) -> dict[str, str]:
    return {
        "name": f"Error {index}",
        "entity_id": f"automation.error_{index}",
        "date": "2026-11-20",
        "error": "Failure",
    }


def test_trace_cache_keeps_exact_count_and_is_bounded() -> None:
    errors = [_error(index) for index in range(10_000)]

    cached, total = _limit_trace_error_cache(errors)

    assert total == 10_000
    assert len(cached) == MAX_SENSOR_LIST_ITEMS
    assert cached == errors[:MAX_SENSOR_LIST_ITEMS]


def test_trace_cache_count_decreases_when_uncached_error_is_fixed() -> None:
    errors = [_error(index) for index in range(150)]
    first_cache, first_total = _limit_trace_error_cache(errors)

    # Error 149 is outside the retained 100 details, but is still counted.
    corrected = errors[:-1]
    next_cache, next_total = _limit_trace_error_cache(corrected)

    assert len(first_cache) == MAX_SENSOR_LIST_ITEMS
    assert first_total == 150
    assert len(next_cache) == MAX_SENSOR_LIST_ITEMS
    assert next_total == 149


def test_trace_cache_replacement_does_not_accumulate() -> None:
    previous_cache, previous_total = _limit_trace_error_cache(
        [_error(index) for index in range(10_000)]
    )
    next_errors = [_error(index) for index in range(25)]
    next_cache, next_total = _limit_trace_error_cache(next_errors)

    assert previous_total == 10_000
    assert len(previous_cache) == MAX_SENSOR_LIST_ITEMS
    assert next_total == 25
    assert next_cache == next_errors
    assert len(next_cache) == 25
