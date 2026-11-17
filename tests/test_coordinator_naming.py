"""Tests for the combined System Info and entity naming scan."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.ha_monitoring import async_reload_entry
from custom_components.ha_monitoring.coordinator import HAMonitoringCoordinator


@pytest.mark.parametrize(
    ("last_check", "cached_stats", "expected_calls"),
    [
        (None, None, 1),
        (datetime(2026, 1, 1, tzinfo=UTC), object(), 0),
        (datetime(2025, 12, 31, 23, 0, tzinfo=UTC), object(), 1),
    ],
)
def test_system_info_and_naming_follow_shared_interval(
    last_check: datetime | None,
    cached_stats: object | None,
    expected_calls: int,
) -> None:
    """The combined scan runs initially, when due, and not between intervals."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    coordinator = SimpleNamespace(
        _last_system_stats_check_time=last_check,
        _cached_system_stats=cached_stats,
        _ha_start_time=now - timedelta(days=1),
        hass=Mock(),
        _cached_id_naming_issues=[],
        _cached_id_naming_checked=0,
        _cached_id_naming_total=0,
        _last_system_info_scan_duration=None,
        _scan_timestamps_changed=False,
    )
    entity_registry = Mock()
    system_stats = AsyncMock(return_value={"uptime": 1})
    naming_result = (
        [{"entity_id": "sensor.old", "expected_entity_id": "sensor.new", "area": None}],
        4,
        1,
    )

    with (
        patch(
            "custom_components.ha_monitoring.coordinator.async_get_system_stats",
            system_stats,
        ),
        patch(
            "custom_components.ha_monitoring.coordinator.get_id_naming_issues",
            return_value=naming_result,
        ) as naming_check,
        patch(
            "custom_components.ha_monitoring.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        asyncio.run(HAMonitoringCoordinator._async_refresh_system_info_and_naming(
            coordinator,
            entity_registry,
            scan_interval_sec=24 * 60 * 60,
            excluded_entities=[],
            excluded_domains=[],
            excluded_globs=[],
            now=now,
        ))

    assert system_stats.await_count == expected_calls
    assert naming_check.call_count == expected_calls

    if expected_calls:
        assert coordinator._cached_system_stats == {"uptime": 1}
        assert coordinator._cached_id_naming_issues == naming_result[0]
        assert coordinator._cached_id_naming_checked == 4
        assert coordinator._cached_id_naming_total == 1
        assert coordinator._last_system_stats_check_time == now
        assert coordinator._scan_timestamps_changed is True
        naming_check.assert_called_once_with(
            coordinator.hass,
            entity_registry,
            excluded_entities=[],
            excluded_domains=[],
            excluded_globs=[],
        )
    else:
        assert coordinator._cached_system_stats is cached_stats
        assert coordinator._last_system_stats_check_time == last_check
        assert coordinator._scan_timestamps_changed is False


def test_forced_refresh_invalidates_shared_scan_cache() -> None:
    """A forced refresh invalidates the timestamp so naming runs immediately."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    coordinator = SimpleNamespace(
        _last_system_stats_check_time=None,
        _cached_system_stats=None,
        _ha_start_time=now - timedelta(days=1),
        hass=Mock(),
        _cached_id_naming_issues=[],
        _cached_id_naming_checked=0,
        _cached_id_naming_total=0,
        _last_system_info_scan_duration=None,
        _scan_timestamps_changed=False,
    )

    with (
        patch(
            "custom_components.ha_monitoring.coordinator.async_get_system_stats",
            new=AsyncMock(return_value={"uptime": 1}),
        ) as system_stats,
        patch(
            "custom_components.ha_monitoring.coordinator.get_id_naming_issues",
            return_value=([], 3, 0),
        ) as naming_check,
        patch(
            "custom_components.ha_monitoring.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        asyncio.run(HAMonitoringCoordinator._async_refresh_system_info_and_naming(
            coordinator,
            Mock(),
            scan_interval_sec=24 * 60 * 60,
            excluded_entities=[],
            excluded_domains=[],
            excluded_globs=[],
            now=now,
        ))

    system_stats.assert_awaited_once()
    naming_check.assert_called_once()


def test_combined_scan_duration_includes_naming() -> None:
    """The System Info duration spans both the System Info and naming calls."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    coordinator = SimpleNamespace(
        _last_system_stats_check_time=None,
        _cached_system_stats=None,
        _ha_start_time=now - timedelta(days=1),
        hass=Mock(),
        _cached_id_naming_issues=[],
        _cached_id_naming_checked=0,
        _cached_id_naming_total=0,
        _last_system_info_scan_duration=None,
        _scan_timestamps_changed=False,
    )

    with (
        patch(
            "custom_components.ha_monitoring.coordinator.async_get_system_stats",
            new=AsyncMock(return_value={"uptime": 1}),
        ),
        patch(
            "custom_components.ha_monitoring.coordinator.get_id_naming_issues",
            return_value=([], 3, 0),
        ),
        patch(
            "custom_components.ha_monitoring.coordinator.time.monotonic",
            side_effect=(10.0, 16.5),
        ),
        patch(
            "custom_components.ha_monitoring.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        asyncio.run(HAMonitoringCoordinator._async_refresh_system_info_and_naming(
            coordinator,
            Mock(),
            scan_interval_sec=24 * 60 * 60,
            excluded_entities=[],
            excluded_domains=[],
            excluded_globs=[],
            now=now,
        ))

    assert coordinator._last_system_info_scan_duration == 6.5


def test_force_refresh_invalidates_system_scan_and_refreshes() -> None:
    """The public forced-refresh method invalidates System Info and naming cadence."""
    coordinator = SimpleNamespace(
        _unsub_ha_started=None,
        _startup_timer_unsub=None,
        _is_ready=False,
        _last_trace_check_time=datetime(2025, 12, 31, tzinfo=UTC),
        _last_system_stats_check_time=datetime(2025, 12, 31, tzinfo=UTC),
        _cached_system_stats={"uptime": 1},
        async_refresh=AsyncMock(),
    )

    asyncio.run(HAMonitoringCoordinator.async_force_refresh(coordinator))

    assert coordinator._is_ready is True
    assert coordinator._last_trace_check_time is None
    assert coordinator._last_system_stats_check_time is None
    assert coordinator._cached_system_stats is None
    coordinator.async_refresh.assert_awaited_once()


def test_config_entry_options_reload_integration() -> None:
    """A configuration update reloads the integration and rebuilds its scan cache."""
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_reload=AsyncMock()),
    )
    entry = SimpleNamespace(entry_id="ha_monitoring_entry")

    asyncio.run(async_reload_entry(hass, entry))

    hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)
