"""Gestionnaire d'inspection des sauvegardes Home Assistant."""

from datetime import datetime
import logging

from homeassistant.components.backup import (
    CreateBackupEvent,
    CreateBackupState,
    async_get_manager,
)
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.util import dt as dt_util

from ..types import MonitoringBackupData

_LOGGER = logging.getLogger(__name__)


def _format_dt(raw_dt: datetime | str | None) -> str | None:
    """Formate une date en ISO 8601 avec le fuseau horaire local."""
    if raw_dt is None:
        return None

    dt_obj = (
        raw_dt
        if isinstance(raw_dt, datetime)
        else dt_util.parse_datetime(raw_dt)
    )

    if dt_obj is None:
        return None

    return dt_util.as_local(dt_obj).isoformat()


def _format_size_bytes(size: int | None) -> str | None:
    """Formate une taille en octets vers une valeur lisible."""
    if size is None or size <= 0:
        return None

    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"

    if size >= 1024:
        return f"{size / 1024:.0f} KB"

    return f"{size} B"


def _get_backup_size_bytes(backup) -> int | None:
    """Retourne la taille du backup sans additionner les copies."""
    if not backup.agents:
        return None

    sizes = [
        agent_backup.size
        for agent_backup in backup.agents.values()
        if agent_backup.size is not None
    ]

    if not sizes:
        return None

    # Un ManagerBackup peut être présent sur plusieurs agents.
    # Les tailles correspondent aux copies du même backup :
    # on ne les additionne donc pas.
    return max(sizes)


def _empty_backup_info() -> MonitoringBackupData:
    """Retourne une structure Backup vide et cohérente."""
    return {
        "is_ok": True,
        "date_last_run": None,
        "date_last_success": None,
        "date_next_schedule": None,
        "size": None,
        "failure": None,
        "failed_agents": [],
        "failed_addons": [],
        "failed_folders": [],
        "current_agent_errors": {},
    }


def _update_from_latest_backup(
    info: MonitoringBackupData,
    backup,
) -> None:
    """Met à jour les informations avec le dernier backup connu."""
    info["date_last_run"] = _format_dt(backup.date)
    info["date_last_success"] = _format_dt(backup.date)
    info["size"] = _format_size_bytes(
        _get_backup_size_bytes(backup)
    )


async def async_get_backup_info(
    hass: HomeAssistant,
    *,
    backup_event: CreateBackupEvent | None = None,
    backup_event_time: datetime | None = None,
    previous_info: MonitoringBackupData | None = None,
) -> MonitoringBackupData:
    """Récupère les informations de sauvegarde via l'API native HA."""
    info = _empty_backup_info()

    try:
        manager = async_get_manager(hass)
        backups, agent_errors = await manager.async_get_backups()

    except HomeAssistantError:
        _LOGGER.debug(
            "[HA Monitoring Backup] Le composant Backup "
            "n'est pas disponible."
        )
        return info

    except Exception as err:
        _LOGGER.warning(
            "[HA Monitoring Backup] Impossible de récupérer "
            "les sauvegardes : %s",
            err,
        )
        return info

    latest_backup = max(
        backups.values(),
        key=lambda backup: backup.date,
        default=None,
    )

    if latest_backup is not None:
        info["date_last_run"] = _format_dt(latest_backup.date)
        info["date_last_success"] = _format_dt(latest_backup.date)
        info["size"] = _format_size_bytes(
            _get_backup_size_bytes(latest_backup)
        )

    # ------------------------------------------------------------------
    # Événement de création de backup
    # ------------------------------------------------------------------
    if backup_event is not None:
        if backup_event.state is CreateBackupState.COMPLETED:
            info["is_ok"] = True
            info["failure"] = None

            if latest_backup is not None:
                _update_from_latest_backup(
                    info,
                    latest_backup,
                )
            elif backup_event_time is not None:
                info["date_last_run"] = _format_dt(
                    backup_event_time
                )
                info["date_last_success"] = info["date_last_run"]

        elif backup_event.state is CreateBackupState.FAILED:
            info["is_ok"] = False

            if backup_event_time is not None:
                info["date_last_run"] = _format_dt(
                    backup_event_time
                )

            # Le reason est conservé tel que fourni par l'API Backup.
            # Aucune traduction ou interprétation locale n'est effectuée.
            info["failure"] = (
                backup_event.reason or "backup_failed"
            )

            # Un backup échoué ne doit pas écraser les informations
            # du dernier backup réussi.
            if previous_info is not None:
                info["date_last_success"] = previous_info.get(
                    "date_last_success"
                )
                info["size"] = previous_info.get("size")

                info["failed_agents"] = previous_info.get(
                    "failed_agents",
                    [],
                )
                info["failed_addons"] = previous_info.get(
                    "failed_addons",
                    [],
                )
                info["failed_folders"] = previous_info.get(
                    "failed_folders",
                    [],
                )

        elif backup_event.state is CreateBackupState.IN_PROGRESS:
            if previous_info is not None:
                info = dict(previous_info)

    elif previous_info is not None:
        # Aucun nouvel événement : conserver l'état précédemment connu.
        info = dict(previous_info)

    # ------------------------------------------------------------------
    # Erreurs des agents
    # ------------------------------------------------------------------
    info["current_agent_errors"] = {
        agent_id: str(error)
        for agent_id, error in agent_errors.items()
    }

    # ------------------------------------------------------------------
    # Informations d'échec du dernier backup connu
    # ------------------------------------------------------------------
    if latest_backup is not None:
        if latest_backup.failed_agent_ids:
            info["failed_agents"] = list(
                latest_backup.failed_agent_ids
            )

        if latest_backup.failed_addons:
            info["failed_addons"] = [
                addon.name or addon.slug
                for addon in latest_backup.failed_addons
            ]

        if latest_backup.failed_folders:
            info["failed_folders"] = [
                folder.value
                for folder in latest_backup.failed_folders
            ]

    # ------------------------------------------------------------------
    # Prochaine sauvegarde automatique
    # ------------------------------------------------------------------
    info["date_next_schedule"] = _format_dt(
        manager.config.data.schedule.next_automatic_backup
    )

    _LOGGER.debug(
        "[HA Monitoring Backup] "
        "last_run=%s | last_success=%s | next_schedule=%s | "
        "size=%s | is_ok=%s | failure=%s",
        info["date_last_run"],
        info["date_last_success"],
        info["date_next_schedule"],
        info["size"],
        info["is_ok"],
        info["failure"],
    )

    return info
