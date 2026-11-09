"""Tests du comportement single_config_entry de HA Monitoring."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ha_monitoring.const import (
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    CONF_SYSTEM_INFO_SCAN_INTERVAL,
    CONF_TRACES_SCAN_INTERVAL,
    DOMAIN,
)


async def test_single_config_entry_is_enforced_by_home_assistant(hass):
    """Une seule entrée de configuration peut être créée."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "section_timings": {
                CONF_STARTUP_DELAY: 0,
                CONF_SCAN_INTERVAL: 30,
                CONF_SYSTEM_INFO_SCAN_INTERVAL: 1,
                CONF_TRACES_SCAN_INTERVAL: 5,
                CONF_OFFLINE_TIMEOUT: 24,
                CONF_BATTERY_LOW_THRESHOLD: 20,
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert second_result["type"] is FlowResultType.ABORT
    assert second_result["reason"] == "single_instance_allowed"
