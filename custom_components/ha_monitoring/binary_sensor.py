"""Capteurs binaires pour l'intégration HA Monitoring."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DATE_LAST_RUN,
    ATTR_DATE_LAST_SUCCESS,
    ATTR_DATE_NEXT_SCHEDULE,
    ATTR_FAILURE,
    ATTR_SIZE,
    DOMAIN,
    ICON_BACKUP,
    ICON_STATUS,
    TRANSLATION_KEY_BACKUP,
    TRANSLATION_KEY_STATUS,
    UNIQUE_ID_BACKUP,
    UNIQUE_ID_STATUS,
)
from .coordinator import HAMonitoringCoordinator
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger("custom_components.ha_monitoring.binary_sensor")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configuration des capteurs binaires via Config Entry."""
    coordinator: HAMonitoringCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        GlobalStatusBinarySensor(coordinator, entry),
        BackupStatusBinarySensor(coordinator, entry),
    ])


class GlobalStatusBinarySensor(HAMonitoringBaseEntity, BinarySensorEntity):
    """Capteur binaire indiquant le statut global du système."""

    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_icon = ICON_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: HAMonitoringCoordinator, entry: ConfigEntry) -> None:
        """Initialise le capteur binaire de statut global."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_STATUS}"
        self.entity_id = f"binary_sensor.{UNIQUE_ID_STATUS}"

    @property
    def is_on(self) -> bool:
        """Renvoie True s'il y a un problème détecté sur le système."""
        if not self.coordinator.data or self.coordinator.data.get("in_startup_delay", False):
            return False

        keys_to_check = (
            "monitoring_addons",
            "monitoring_integrations",
            "monitoring_automations",
            "monitoring_scripts",
        )
        for key in keys_to_check:
            data = self.coordinator.data.get(key, {})
            if data.get("total", 0) > 0:
                return True

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs détaillés du statut global et des métriques système."""
        if not self.coordinator.data:
            return {}

        stats = self.coordinator.data.get("system_stats", {})

        return {
            "in_startup_delay": self.coordinator.data.get("in_startup_delay", False),
            # HA / OS : versions et démarrages
            "ha_version": stats.get("ha_version"),
            "ha_last_boot": stats.get("ha_last_boot"),
            "os_version": stats.get("os_version"),
            "os_last_boot": stats.get("os_last_boot"),
            # Inventaire / Comptages
            "devices_count": stats.get("devices_count", 0),
            "entities_count": stats.get("entities_count", 0),
            "automations_count": stats.get("automations_count", 0),
            "scripts_count": stats.get("scripts_count", 0),
            "integrations_count": stats.get("integrations_count", 0),
            "custom_integrations_count": stats.get("custom_integrations_count", 0),
            # Recorder et Base de données
            "recorder_commit_interval": stats.get("recorder_commit_interval"),
            "recorder_keep_days": stats.get("recorder_keep_days"),
            "recorder_auto_purge": stats.get("recorder_auto_purge"),
            "recorder_auto_repack": stats.get("recorder_auto_repack"),
            "database_size_mb": stats.get("database_size_mb"),
        }


class BackupStatusBinarySensor(HAMonitoringBaseEntity, BinarySensorEntity):
    """Capteur binaire indiquant si la dernière sauvegarde a réussi."""

    _attr_translation_key = TRANSLATION_KEY_BACKUP
    _attr_icon = ICON_BACKUP

    def __init__(self, coordinator: HAMonitoringCoordinator, entry: ConfigEntry) -> None:
        """Initialise le capteur binaire d'état de la sauvegarde."""
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs détaillés de la dernière sauvegarde."""
        if not self.coordinator.data:
            return {
                ATTR_DATE_LAST_RUN: None,
                ATTR_DATE_LAST_SUCCESS: None,
                ATTR_DATE_NEXT_SCHEDULE: None,
                ATTR_SIZE: None,
                ATTR_FAILURE: None,
            }

        backup_info = self.coordinator.data.get("monitoring_backup", {})
        return {
            ATTR_DATE_LAST_RUN: backup_info.get("date_last_run"),
            ATTR_DATE_LAST_SUCCESS: backup_info.get("date_last_success"),
            ATTR_DATE_NEXT_SCHEDULE: backup_info.get("date_next_schedule"),
            ATTR_SIZE: backup_info.get("size"),
            ATTR_FAILURE: backup_info.get("failure"),
        }
