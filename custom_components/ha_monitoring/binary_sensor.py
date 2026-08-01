"""Capteur binaire global pour HA Monitoring."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    UNIQUE_ID_STATUS,
    TRANSLATION_KEY_STATUS,
    ICON_STATUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Ajoute le capteur binaire via Config Entry."""
    scan_interval_sec = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=int(scan_interval_sec))

    async_add_entities([HAMonitoringStatusSensor(hass, scan_interval)], True)


class HAMonitoringStatusSensor(BinarySensorEntity):
    """Capteur binaire indiquant si au moins une erreur est présente sur le système."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_unique_id = UNIQUE_ID_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_STATUS

    def __init__(self, hass, scan_interval):
        self._hass = hass
        self._attr_scan_interval = scan_interval
        self._is_on = False
        self._summary = {}

    @property
    def is_on(self):
        return self._is_on

    @property
    def extra_state_attributes(self):
        return self._summary

    async def async_update(self):
        monitored_sensors = [
            "sensor.add_ons_en_erreur",
            "sensor.integrations_en_erreur",
            "sensor.automations_en_erreur",
            "sensor.scripts_en_erreur",
        ]

        has_problem = False
        summary = {}

        for entity_id in monitored_sensors:
            state_obj = self._hass.states.get(entity_id)
            if state_obj:
                try:
                    count = int(state_obj.state)
                    if count > 0:
                        has_problem = True
                    summary[entity_id] = count
                except (ValueError, TypeError):
                    summary[entity_id] = 0
            else:
                summary[entity_id] = 0

        self._is_on = has_problem
        self._summary = summary
