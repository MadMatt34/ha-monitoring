"""Capteurs binaires pour l'intégration HA Monitoring."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DATE_LAST_RUN,
    ATTR_DATE_LAST_SUCCESS,
    ATTR_DATE_NEXT_SCHEDULE,
    ATTR_FAILURE,
    ATTR_SIZE,
    ATTR_STARTUP_DELAY,
    ICON_BACKUP,
    ICON_STATUS,
    TRANSLATION_KEY_BACKUP,
    TRANSLATION_KEY_STATUS,
    UNIQUE_ID_BACKUP,
    UNIQUE_ID_STATUS,
)
from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)
from .entity import HAMonitoringBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les capteurs binaires via Config Entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            GlobalStatusBinarySensor(
                coordinator,
                entry,
            ),
            BackupStatusBinarySensor(
                coordinator,
                entry,
            ),
        ]
    )


class GlobalStatusBinarySensor(
    HAMonitoringBaseEntity,
    BinarySensorEntity,
):
    """Capteur binaire indiquant le statut global du système."""

    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_icon = ICON_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: HAMonitoringConfigEntry,
    ) -> None:
        """Initialise le capteur binaire de statut global."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.entry_id}_{UNIQUE_ID_STATUS}"
        )

        # Entity ID volontairement statique.
        self.entity_id = f"binary_sensor.{UNIQUE_ID_STATUS}"

    @override
    @property
    def is_on(self) -> bool:
        """Retourne True si un problème est détecté."""
        data = self.coordinator.data

        if data["startup_delay"]:
            return False

        return any(
            data[key]["total"] > 0
            for key in (
                "monitoring_addons",
                "monitoring_integrations",
                "monitoring_automations",
                "monitoring_scripts",
            )
        )

    @override
    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Retourne les métriques système détaillées."""
        data = self.coordinator.data
        stats = data["system_stats"]

        return {
            ATTR_STARTUP_DELAY: data["startup_delay"],
            "ha_version": stats.get("ha_version"),
            "ha_last_boot": stats.get("ha_last_boot"),
            "os_version": stats.get("os_version"),
            "os_last_boot": stats.get("os_last_boot"),
            "devices_count": stats.get("devices_count", 0),
            "entities_count": stats.get("entities_count", 0),
            "automations_count": stats.get(
                "automations_count",
                0,
            ),
            "scripts_count": stats.get(
                "scripts_count",
                0,
            ),
            "integrations_count": stats.get(
                "integrations_count",
                0,
            ),
            "custom_integrations_count": stats.get(
                "custom_integrations_count",
                0,
            ),
            "recorder_commit_interval": stats.get(
                "recorder_commit_interval"
            ),
            "recorder_keep_days": stats.get(
                "recorder_keep_days"
            ),
            "recorder_auto_purge": stats.get(
                "recorder_auto_purge"
            ),
            "recorder_auto_repack": stats.get(
                "recorder_auto_repack"
            ),
            "database_size_mb": stats.get(
                "database_size_mb"
            ),
        }


class BackupStatusBinarySensor(
    HAMonitoringBaseEntity,
    BinarySensorEntity,
):
    """Capteur binaire indiquant si la dernière sauvegarde a réussi."""

    _attr_translation_key = TRANSLATION_KEY_BACKUP
    _attr_icon = ICON_BACKUP

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: HAMonitoringConfigEntry,
    ) -> None:
        """Initialise le capteur binaire d'état de la sauvegarde."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.entry_id}_{UNIQUE_ID_BACKUP}"
        )

        # Entity ID volontairement statique.
        self.entity_id = f"binary_sensor.{UNIQUE_ID_BACKUP}"

    @override
    @property
    def is_on(self) -> bool:
        """Retourne True si la dernière sauvegarde est considérée OK."""
        data = self.coordinator.data

        if data["startup_delay"]:
            return True

        return data["monitoring_backup"]["is_ok"]

    @override
    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Retourne les détails de la dernière sauvegarde."""
        backup = self.coordinator.data["monitoring_backup"]

        return {
            ATTR_DATE_LAST_RUN: backup["date_last_run"],
            ATTR_DATE_LAST_SUCCESS: backup["date_last_success"],
            ATTR_DATE_NEXT_SCHEDULE: backup["date_next_schedule"],
            ATTR_SIZE: backup["size"],
            ATTR_FAILURE: backup["failure"],
        }
