"""Capteurs binaires pour l'intégration HA Monitoring."""
from datetime import datetime, timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    ICON_STATUS,
    ICON_BACKUP,
    UNIQUE_ID_STATUS,
    UNIQUE_ID_BACKUP,
    TRANSLATION_KEY_STATUS,
    TRANSLATION_KEY_BACKUP,
    ATTR_DATE_SAUVEGARDE,
    ATTR_DATE_DERNIERE_REUSSIE,
    ATTR_DATE_PROCHAINE_PLANIFIEE,
    ATTR_TAILLE_SAUVEGARDE,
)

_LOGGER = logging.getLogger(__name__)


def is_hassio_running(hass) -> bool:
    """Vérifie si Home Assistant tourne sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs binaires via Config Entry."""
    scan_interval_sec = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=int(scan_interval_sec))

    async_add_entities([
        GlobalStatusBinarySensor(hass, entry, scan_interval),
        BackupStatusBinarySensor(hass, entry, scan_interval),
    ], True)


class GlobalStatusBinarySensor(BinarySensorEntity):
    """Capteur binaire indiquant le statut global du système."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_STATUS
    _attr_unique_id = UNIQUE_ID_STATUS
    _attr_icon = ICON_STATUS
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hass, entry, scan_interval):
        self._hass = hass
        self._entry = entry
        self._attr_scan_interval = scan_interval
        self._is_on = False

    @property
    def is_on(self):
        """Renvoie True s'il y a un problème sur le système."""
        return self._is_on

    async def async_update(self):
        """Vérifie si l'un des capteurs de surveillance est en alerte."""
        try:
            problem = False
            sensors_to_check = [
                "sensor.add_ons_en_erreur",
                "sensor.integrations_en_erreur",
                "sensor.automations_en_erreur",
                "sensor.scripts_en_erreur",
            ]

            for entity_id in sensors_to_check:
                state_obj = self._hass.states.get(entity_id)
                if state_obj and state_obj.state not in ("unknown", "unavailable"):
                    try:
                        if int(state_obj.state) > 0:
                            problem = True
                            break
                    except ValueError:
                        pass

            self._is_on = problem
        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring (Statut global) : %s", err)


class BackupStatusBinarySensor(BinarySensorEntity):
    """Capteur binaire indiquant si la dernière sauvegarde a réussi."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_BACKUP
    _attr_unique_id = UNIQUE_ID_BACKUP
    _attr_icon = ICON_BACKUP

    def __init__(self, hass, entry, scan_interval):
        self._hass = hass
        self._entry = entry
        self._attr_scan_interval = scan_interval
        self._is_on = True
        self._date_sauvegarde = None
        self._date_derniere_reussie = None
        self._date_prochaine_planifiee = None
        self._taille_sauvegarde = None

    @property
    def is_on(self):
        """Renvoie True si la dernière sauvegarde a réussi, False sinon."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Attributs de la dernière sauvegarde."""
        return {
            ATTR_DATE_SAUVEGARDE: self._date_sauvegarde,
            ATTR_DATE_DERNIERE_REUSSIE: self._date_derniere_reussie,
            ATTR_DATE_PROCHAINE_PLANIFIEE: self._date_prochaine_planifiee,
            ATTR_TAILLE_SAUVEGARDE: self._taille_sauvegarde,
        }

    def _format_size(self, size_bytes_or_mb):
        """Formate la taille en Mo ou Go."""
        if size_bytes_or_mb is None:
            return None
        
        if isinstance(size_bytes_or_mb, (int, float)):
            if size_bytes_or_mb > 1024 * 1024:
                mb = size_bytes_or_mb / (1024 * 1024)
            else:
                mb = size_bytes_or_mb

            if mb >= 1024:
                return f"{round(mb / 1024, 2)} Go"
            return f"{round(mb, 2)} Mo"
        return str(size_bytes_or_mb)

    async def async_update(self):
        """Interroge le gestionnaire de sauvegardes Supervisor / Core."""
        backups_list = []
        next_scheduled = None

        # 1. Tentative via l'API Supervisor / HASSIO sans dépendance d'import
        if is_hassio_running(self._hass):
            try:
                client = self._hass.data.get("hassio")
                if client:
                    backups_info = None
                    if hasattr(client, "async_get_backups"):
                        backups_info = await client.async_get_backups()
                    elif hasattr(client, "get_backups"):
                        backups_info = await client.get_backups()
                    elif hasattr(client, "send_command"):
                        backups_info = await client.send_command("/backups", method="get")

                    if isinstance(backups_info, dict) and "backups" in backups_info:
                        backups_list = backups_info.get("backups", [])
            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Hassio : %s", err)

        # 2. Fallback via le module Backup natif de Home Assistant Core
        if not backups_list and "backup" in self._hass.data:
            try:
                backup_manager = self._hass.data["backup"]
                if hasattr(backup_manager, "backups"):
                    raw_backups = backup_manager.backups
                    if isinstance(raw_backups, dict):
                        for b in raw_backups.values():
                            backups_list.append({
                                "slug": getattr(b, "slug", None) or getattr(b, "id", ""),
                                "name": getattr(b, "name", ""),
                                "date": getattr(b, "date", None),
                                "size": getattr(b, "size", 0),
                                "failed": getattr(b, "failed", False),
                            })
                
                if hasattr(backup_manager, "config") and hasattr(backup_manager.config, "create_backup"):
                    schedule = getattr(backup_manager.config, "schedule", None)
                    if schedule and hasattr(schedule, "next_execution"):
                        next_scheduled = schedule.next_execution
            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Backup Core : %s", err)

        if not backups_list:
            self._is_on = False
            self._date_sauvegarde = None
            self._date_derniere_reussie = None
            self._date_prochaine_planifiee = str(next_scheduled) if next_scheduled else "Non configurée"
            self._taille_sauvegarde = None
            return

        # Trier les sauvegardes de la plus récente à la plus ancienne
        def get_date(b):
            d = b.get("date")
            if isinstance(d, datetime):
                return dt_util.as_utc(d)
            if isinstance(d, str):
                parsed = dt_util.parse_datetime(d)
                if parsed:
                    return dt_util.as_utc(parsed)
            return datetime.min.replace(tzinfo=dt_util.UTC)

        sorted_backups = sorted(backups_list, key=get_date, reverse=True)
        latest_backup = sorted_backups[0]

        is_failed = latest_backup.get("failed", False) or latest_backup.get("status") == "failed"
        self._is_on = not is_failed

        last_dt = get_date(latest_backup)
        self._date_sauvegarde = last_dt.isoformat() if last_dt != datetime.min.replace(tzinfo=dt_util.UTC) else str(latest_backup.get("date"))

        last_successful_dt = None
        for b in sorted_backups:
            if not b.get("failed", False) and b.get("status") != "failed":
                last_successful_dt = get_date(b)
                break

        if last_successful_dt and last_successful_dt != datetime.min.replace(tzinfo=dt_util.UTC):
            self._date_derniere_reussie = last_successful_dt.isoformat()
        else:
            self._date_derniere_reussie = self._date_sauvegarde if self._is_on else "Aucune"

        if next_scheduled:
            if isinstance(next_scheduled, datetime):
                self._date_prochaine_planifiee = next_scheduled.isoformat()
            else:
                self._date_prochaine_planifiee = str(next_scheduled)
        else:
            self._date_prochaine_planifiee = "Non planifiée"

        self._taille_sauvegarde = self._format_size(latest_backup.get("size"))
