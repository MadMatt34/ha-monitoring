"""Capteurs binaires pour l'intégration HA Monitoring."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import (
    ATTR_DATE_LAST_RUN,
    ATTR_DATE_LAST_SUCCESS,
    ATTR_DATE_NEXT_SCHEDULE,
    ATTR_SIZE,
    ATTR_FAILURE,
    DOMAIN,
    ICON_BACKUP,
    ICON_STATUS,
    TRANSLATION_KEY_BACKUP,
    TRANSLATION_KEY_STATUS,
    UNIQUE_ID_BACKUP,
    UNIQUE_ID_STATUS,
)
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs binaires via Config Entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        GlobalStatusBinarySensor(coordinator, entry),
        BackupStatusBinarySensor(coordinator, entry),
    ])


class GlobalStatusBinarySensor(HAMonitoringBaseEntity, BinarySensorEntity):
    """Capteur binaire indiquant le statut global du système."""

    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_icon = ICON_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_STATUS}"
        self.entity_id = f"binary_sensor.{UNIQUE_ID_STATUS}"

    @property
    def is_on(self) -> bool:
        """Renvoie True s'il y a un problème sur le système."""
        if not self.coordinator.data or self.coordinator.data.get("in_startup_delay", False):
            return False

        keys_to_check = [
            "monitoring_addons",
            "monitoring_integrations",
            "monitoring_automations",
            "monitoring_scripts",
        ]
        for key in keys_to_check:
            data = self.coordinator.data.get(key, {})
            if data.get("total", 0) > 0:
                return True
        return False


class BackupStatusBinarySensor(HAMonitoringBaseEntity, BinarySensorEntity):
    """Capteur binaire indiquant si la dernière sauvegarde a réussi."""

    _attr_translation_key = TRANSLATION_KEY_BACKUP
    _attr_icon = ICON_BACKUP

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_BACKUP}"
        self.entity_id = f"binary_sensor.{UNIQUE_ID_BACKUP}"

    @property
    def is_on(self) -> bool:
        """Renvoie True si la dernière sauvegarde a réussi, False sinon."""
        if not self.coordinator.data or self.coordinator.data.get("in_startup_delay", False):
            return True

        backup_info = self.coordinator.data.get("monitoring_backup", {})
        return backup_info.get("is_ok", True)

    @property
    def extra_state_attributes(self) -> dict:
        """Attributs de la dernière sauvegarde."""
        if not self.coordinator.data:
            return {}

        backup_info = self.coordinator.data.get("monitoring_backup", {})
        return {
            ATTR_DATE_LAST_RUN: backup_info.get("date_last_run"),
            ATTR_DATE_LAST_SUCCESS: backup_info.get("date_last_success"),
            ATTR_DATE_NEXT_SCHEDULE: backup_info.get("date_next_schedule"),
            ATTR_SIZE: backup_info.get("size"),
            ATTR_FAILURE: backup_info.get("failure"),
        }
