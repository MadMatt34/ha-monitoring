"""Gestionnaire d'inspection des sauvegardes Home Assistant."""

from datetime import datetime
import logging

from homeassistant.components.backup import (
    CreateBackupEvent,
    CreateBackupState,
    ManagerBackup,
    async_get_manager,
)
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
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


def _get_backup_size_bytes(
    backup: ManagerBackup,
) -> int | None:
    """Retourne la taille représentative du backup."""
    if not backup.agents:
        return None

    return max(
        agent_backup.size
        for agent_backup in backup.agents.values()
    )


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


def _apply_backup_details(
    info: MonitoringBackupData,
    backup: ManagerBackup,
) -> None:
    """Applique les informations du dernier backup connu."""
    info["date_last_run"] = _format_dt(backup.date)
    info["date_last_success"] = _format_dt(backup.date)
    info["size"] = _format_size_bytes(
        _get_backup_size_bytes(backup)
    )
    info["failed_agents"] = list(backup.failed_agent_ids)
    info["failed_addons"] = [
        addon.name or addon.slug
        for addon in backup.failed_addons
    ]
    info["failed_folders"] = [
        folder.value
        for folder in backup.failed_folders
    ]


def _apply_current_agent_errors(
    info: MonitoringBackupData,
    agent_errors: dict[str, Exception],
) -> None:
    """Applique les erreurs actuelles retournées par les agents."""
    info["current_agent_errors"] = {
        agent_id: str(error)
        for agent_id, error in agent_errors.items()
    }


async def _translate_failure_reason(
    hass: HomeAssistant,
    reason: str,
) -> str:
    """Traduit un code d'erreur Backup avec le système natif HA."""
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "exceptions",
        integrations={DOMAIN},
    )

    translation_key = (
        f"component.{DOMAIN}.exceptions.{reason}.message"
    )

    return translations.get(translation_key, reason)


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

    latest_backup = max(
        backups.values(),
        key=lambda backup: backup.date,
        default=None,
    )

    _apply_current_agent_errors(
        info,
        agent_errors,
    )

    # ------------------------------------------------------------------
    # Aucun nouvel événement.
    #
    # Si un état a déjà été connu par HA Monitoring, on le conserve.
    # Le dernier ManagerBackup ne doit PAS écraser un échec courant.
    # ------------------------------------------------------------------
    if backup_event is None:
        if previous_info is not None:
            info = dict(previous_info)
            _apply_current_agent_errors(
                info,
                agent_errors,
            )

        elif latest_backup is not None:
            _apply_backup_details(
                info,
                latest_backup,
            )

    # ------------------------------------------------------------------
    # Backup réussi.
    #
    # Un COMPLETED constitue une nouvelle référence : l'éventuel échec
    # précédent doit disparaître.
    # ------------------------------------------------------------------
    elif backup_event.state is CreateBackupState.COMPLETED:
        info["is_ok"] = True
        info["failure"] = None

        if latest_backup is not None:
            _apply_backup_details(
                info,
                latest_backup,
            )
        elif backup_event_time is not None:
            formatted_time = _format_dt(
                backup_event_time
            )

            info["date_last_run"] = formatted_time
            info["date_last_success"] = formatted_time

            if previous_info is not None:
                info["size"] = previous_info.get("size")

    # ------------------------------------------------------------------
    # Backup échoué.
    #
    # L'événement courant devient le dernier run, mais le dernier succès
    # reste celui connu précédemment.
    # ------------------------------------------------------------------
    elif backup_event.state is CreateBackupState.FAILED:
        info["is_ok"] = False

        if backup_event_time is not None:
            info["date_last_run"] = _format_dt(
                backup_event_time
            )

        reason = backup_event.reason or "backup_failed"

        info["failure"] = await _translate_failure_reason(
            hass,
            reason,
        )

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

        elif latest_backup is not None:
            # Premier état connu après un échec :
            # le dernier backup déjà disponible reste le dernier succès.
            info["date_last_success"] = _format_dt(
                latest_backup.date
            )
            info["size"] = _format_size_bytes(
                _get_backup_size_bytes(latest_backup)
            )
            info["failed_agents"] = list(
                latest_backup.failed_agent_ids
            )
            info["failed_addons"] = [
                addon.name or addon.slug
                for addon in latest_backup.failed_addons
            ]
            info["failed_folders"] = [
                folder.value
                for folder in latest_backup.failed_folders
            ]

    # ------------------------------------------------------------------
    # Backup en cours.
    # ------------------------------------------------------------------
    elif backup_event.state is CreateBackupState.IN_PROGRESS:
        if previous_info is not None:
            info = dict(previous_info)

            _apply_current_agent_errors(
                info,
                agent_errors,
            )

    # ------------------------------------------------------------------
    # Planning automatique.
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
