"""Capteur binaire global pour HA Monitoring."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    UNIQUE_ID_STATUS,
    TRANSLATION_KEY_STATUS,
    ICON_STATUS,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Ajoute le capteur binaire de surveillance."""
    async_add_entities([HAMonitoringStatusSensor(hass)], True)


class HAMonitoringStatusSensor(BinarySensorEntity):
    """Capteur binaire indiquant si au moins une erreur est présente sur le système."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_unique_id = UNIQUE_ID_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_STATUS

    def __init__(self, hass):
        self._hass = hass
        self._is_on = False
        self._summary = {}

    @property
    def is_on(self):
        """Retourne True (on) si au moins une erreur est détectée."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Retourne un dictionnaire récapitulatif des compteurs d'erreurs."""
        return self._summary

    async def async_update(self):
        """Vérifie l'état des 4 capteurs de surveillance."""
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
