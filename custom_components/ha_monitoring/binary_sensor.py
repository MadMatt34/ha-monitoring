"""Capteurs binaires pour l'intégration HA Monitoring."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DATE_DERNIERE_REUSSIE,
    ATTR_DATE_PROCHAINE_PLANIFIEE,
    ATTR_DATE_SAUVEGARDE,
    ATTR_TAILLE_SAUVEGARDE,
    DOMAIN,
    ICON_BACKUP,
    ICON_STATUS,
    TRANSLATION_KEY_BACKUP,
    TRANSLATION_KEY_STATUS,
    UNIQUE_ID_BACKUP,
    UNIQUE_ID_STATUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs binaires via Config Entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        GlobalStatusBinarySensor(coordinator, entry),
        BackupStatusBinarySensor(coordinator, entry),
    ])


class GlobalStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Capteur binaire indiquant le statut global du système."""

    _attr_has_entity_name = True
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


class BackupStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Capteur binaire indiquant si la dernière sauvegarde a réussi."""

    _attr_has_entity_name = True
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
            ATTR_DATE_SAUVEGARDE: backup_info.get("date_sauvegarde"),
            ATTR_DATE_DERNIERE_REUSSIE: backup_info.get("date_derniere_reussie"),
            ATTR_DATE_PROCHAINE_PLANIFIEE: backup_info.get("date_prochaine_planifiee"),
            ATTR_TAILLE_SAUVEGARDE: backup_info.get("taille_sauvegarde"),
        }
