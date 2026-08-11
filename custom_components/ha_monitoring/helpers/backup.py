"""Gestionnaire d'inspection des sauvegardes basé exclusivement sur les APIs natives HA."""

import contextlib
import dataclasses
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..types import MonitoringBackupData

_LOGGER = logging.getLogger(__name__)


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convertit de manière ultra-robuste tout objet/dataclass HA en dictionnaire."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if not str(k).startswith("_")}

    res: dict[str, Any] = {}
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        with contextlib.suppress(Exception):
            res = obj.to_dict()
    elif hasattr(obj, "as_dict") and callable(obj.as_dict):
        with contextlib.suppress(Exception):
            res = obj.as_dict()
    elif dataclasses.is_dataclass(obj):
        with contextlib.suppress(Exception):
            res = dataclasses.asdict(obj)
    elif hasattr(obj, "__dict__"):
        res = vars(obj)

    return {k: v for k, v in res.items() if not str(k).startswith("_")}


def _format_dt(raw_dt: Any) -> str | None:
    """Formate une date au format ISO 8601 en heure locale avec fuseau horaire."""
    if not raw_dt:
        return None

    s_val = str(raw_dt).strip()
    if s_val.lower() in ("unknown", "unavailable", "blocked", "none", "null", "inconnu", ""):
        return None

    dt_obj: datetime | None = None

    if isinstance(raw_dt, datetime):
        dt_obj = raw_dt
    elif isinstance(raw_dt, (int, float)):
        with contextlib.suppress(Exception):
            dt_obj = datetime.fromtimestamp(raw_dt, tz=dt_util.UTC)
    else:
        with contextlib.suppress(Exception):
            dt_obj = dt_util.parse_datetime(s_val)

    if dt_obj:
        try:
            return dt_util.as_local(dt_obj).isoformat()
        except Exception:
            return dt_obj.isoformat()

    return s_val if len(s_val) >= 8 else None


def _format_size_bytes(bytes_val: Any) -> str | None:
    """Formate la taille en octets vers une chaîne lisible (KB, MB, GB)."""
    if bytes_val is None:
        return None
    try:
        val = float(bytes_val)
        if val > 0:
            if val >= 1024 * 1024 * 1024:
                return f"{val / (1024 * 1024 * 1024):.2f} GB"
            if val >= 1024 * 1024:
                return f"{val / (1024 * 1024):.1f} MB"
            if val >= 1024:
                return f"{val / 1024:.0f} KB"
            return f"{val:.0f} B"
    except (ValueError, TypeError):
        pass
    return str(bytes_val)


def _extract_backup_objects(raw: Any) -> list[Any]:
    """Aplatit et extrait la liste de tous les objets ManagerBackup indifféremment de la structure."""
    if not raw:
        return []

    if isinstance(raw, dict) or (hasattr(raw, "values") and callable(raw.values)):
        res = []
        for item in raw.values():
            res.extend(_extract_backup_objects(item))
        return res

    if isinstance(raw, (list, tuple, set)):
        res = []
        for item in raw:
            res.extend(_extract_backup_objects(item))
        return res

    return [raw]


def _find_scalar_field(
    data: dict[str, Any], candidate_keys: tuple[str, ...], depth: int = 0
) -> Any:
    """Recherche une valeur scalaire avec sécurité anti-récursion (depth max = 4)."""
    if depth > 4 or not isinstance(data, dict):
        return None

    for key in candidate_keys:
        if key in data and data[key] is not None:
            val = data[key]
            if isinstance(val, (datetime, str, int, float)):
                return val

    for k, v in data.items():
        if str(k).startswith("_"):
            continue
        if isinstance(v, dict):
            res = _find_scalar_field(v, candidate_keys, depth + 1)
            if res is not None:
                return res
        elif dataclasses.is_dataclass(v) or hasattr(v, "__dict__"):
            res = _find_scalar_field(_to_dict(v), candidate_keys, depth + 1)
            if res is not None:
                return res

    return None


def _find_collection_field(data: dict[str, Any], candidate_keys: tuple[str, ...]) -> list[Any]:
    """Recherche une collection dans un dictionnaire d'objet HA."""
    for key in candidate_keys:
        value = data.get(key)
        if isinstance(value, (list, tuple, set)):
            return list(value)
    return []


def _get_backup_size_bytes(b_obj: Any) -> int | None:
    """Extrait la taille en octets du fichier de sauvegarde sans additionner les copies d'agents."""
    b_dict = _to_dict(b_obj)
    sz = _find_scalar_field(b_dict, ("size", "bytes", "total_size", "file_size"))
    if sz is not None:
        try:
            val = int(sz)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass

    agents = getattr(b_obj, "agents", None)
    if isinstance(agents, dict) and agents:
        agent_sizes = []
        for agent in agents.values():
            a_sz = getattr(agent, "size", None)
            if a_sz is None and isinstance(agent, dict):
                a_sz = agent.get("size")
            if a_sz is not None:
                try:
                    val = int(a_sz)
                    if val > 0:
                        agent_sizes.append(val)
                except (ValueError, TypeError):
                    pass
        if agent_sizes:
            return max(agent_sizes)

    return None


def _get_failure_translation_key(reason: str) -> str:
    """Construit la clé de traduction d'une cause de sauvegarde."""
    return reason


def _load_failure_translation(hass: HomeAssistant, reason: str) -> str | None:
    """Charge le texte traduit de la cause depuis translations/<lang>.json."""
    language = (hass.config.language or "en").replace("_", "-").split("-")[0]
    translations_path = Path(__file__).resolve().parent.parent / "translations" / f"{language}.json"

    if not translations_path.is_file():
        return None

    try:
        data = json.loads(translations_path.read_text(encoding="utf-8"))
        return (
            data.get("exceptions", {}).get(_get_failure_translation_key(reason), {}).get("message")
        )
    except (OSError, json.JSONDecodeError, AttributeError):
        _LOGGER.warning(
            "[HA Monitoring Backup] Impossible de charger la traduction de %s depuis %s",
            reason,
            translations_path,
        )
        return None


async def async_get_backup_info(
    hass: HomeAssistant,
    *,
    backup_event: Any | None = None,
    backup_event_time: datetime | None = None,
    previous_info: MonitoringBackupData | None = None,
) -> MonitoringBackupData:
    """Récupère les informations de sauvegarde via les APIs natives de Home Assistant."""
    info: MonitoringBackupData = {
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

    if "backup" not in hass.data:
        return info

    try:
        b_data = hass.data["backup"]
        manager = getattr(b_data, "manager", b_data)

        backups_raw: dict[str, Any] = {}
        agent_errors: dict[str, Exception] = {}

        if hasattr(manager, "async_get_backups"):
            try:
                result = await manager.async_get_backups()
                if isinstance(result, tuple) and len(result) == 2:
                    backups_raw, agent_errors = result
                else:
                    backups_raw = result
            except Exception as err_m:
                _LOGGER.warning(
                    "[HA Monitoring Backup] Appel async_get_backups() échoué: %s", err_m
                )

        backup_list = (
            list(backups_raw.values())
            if isinstance(backups_raw, dict)
            else _extract_backup_objects(backups_raw)
        )

        valid_backups: list[tuple[str, Any, int | None, Any]] = []
        for backup_obj in backup_list:
            b_dict = _to_dict(backup_obj)
            raw_date = _find_scalar_field(
                b_dict, ("date", "created", "created_at", "timestamp", "utc_date")
            )
            if not raw_date:
                continue
            backup_id = _find_scalar_field(b_dict, ("backup_id", "slug", "id"))
            valid_backups.append(
                (str(raw_date), raw_date, _get_backup_size_bytes(backup_obj), backup_id)
            )

        valid_backups.sort(key=lambda item: item[0], reverse=True)
        latest_backup = valid_backups[0] if valid_backups else None

        event_state = getattr(backup_event, "state", None) if backup_event else None
        event_state_value = getattr(event_state, "value", event_state)
        if event_state_value == "completed":
            if latest_backup:
                _, latest_date, latest_size, _ = latest_backup
                info["date_last_run"] = _format_dt(latest_date)
                info["date_last_success"] = info["date_last_run"]
                info["size"] = _format_size_bytes(latest_size)
            elif backup_event_time:
                info["date_last_run"] = _format_dt(backup_event_time)
                info["date_last_success"] = info["date_last_run"]
            info["is_ok"] = True
            info["failure"] = None

        elif event_state_value == "failed":
            if backup_event_time:
                info["date_last_run"] = _format_dt(backup_event_time)
            elif latest_backup:
                info["date_last_run"] = _format_dt(latest_backup[1])

            reason = backup_event.reason if backup_event else None
            reason = reason or "backup_failed"
            info["is_ok"] = False
            info["failure"] = _load_failure_translation(hass, reason) or reason

            if latest_backup:
                latest_backup_obj = next(
                    (
                        obj
                        for obj in backup_list
                        if _find_scalar_field(_to_dict(obj), ("backup_id", "slug", "id"))
                        == latest_backup[3]
                    ),
                    None,
                )
                if latest_backup_obj is not None:
                    latest_dict = _to_dict(latest_backup_obj)
                    info["failed_agents"] = list(
                        _find_collection_field(latest_dict, ("failed_agent_ids",))
                    )
                    info["failed_addons"] = list(
                        _find_collection_field(latest_dict, ("failed_addons",))
                    )
                    info["failed_folders"] = list(
                        _find_collection_field(latest_dict, ("failed_folders",))
                    )

            info["current_agent_errors"] = {
                str(agent_id): str(error) for agent_id, error in agent_errors.items()
            }

            if previous_info and previous_info.get("date_last_success"):
                info["date_last_success"] = previous_info["date_last_success"]
            elif latest_backup:
                info["date_last_success"] = _format_dt(latest_backup[1])

            if latest_backup:
                info["size"] = _format_size_bytes(latest_backup[2])

        elif latest_backup:
            _, latest_date, latest_size, _ = latest_backup
            info["date_last_run"] = _format_dt(latest_date)
            info["date_last_success"] = info["date_last_run"]
            info["size"] = _format_size_bytes(latest_size)

        if agent_errors:
            _LOGGER.debug(
                "[HA Monitoring Backup] Erreurs lors de la lecture des agents: %s",
                agent_errors,
            )

        config_raw = None
        if hasattr(manager, "async_get_config"):
            with contextlib.suppress(Exception):
                config_raw = await manager.async_get_config()
        if config_raw is None and hasattr(manager, "config"):
            config_raw = manager.config

        if config_raw:
            data_obj = getattr(config_raw, "data", config_raw)
            schedule_obj = (
                getattr(data_obj, "schedule", None)
                if not isinstance(data_obj, dict)
                else data_obj.get("schedule")
            )
            next_dt = (
                getattr(schedule_obj, "next_automatic_backup", None)
                if not isinstance(schedule_obj, dict)
                else (schedule_obj.get("next_automatic_backup") if schedule_obj else None)
            )
            if next_dt:
                info["date_next_schedule"] = _format_dt(next_dt)
            else:
                next_schedule = _find_scalar_field(
                    _to_dict(config_raw),
                    (
                        "next_automatic_backup",
                        "next_backup",
                        "next_run",
                        "next_scheduled",
                        "next_execution",
                    ),
                )
                if next_schedule:
                    info["date_next_schedule"] = _format_dt(next_schedule)

    except Exception as err:
        _LOGGER.warning("[HA Monitoring Backup] Erreur HA Core Manager: %s", err)

    if backup_event is None and previous_info and previous_info.get("failure"):
        info["failure"] = previous_info["failure"]
        info["is_ok"] = previous_info.get("is_ok", False)
        info["date_last_run"] = previous_info.get("date_last_run") or info["date_last_run"]
        info["date_last_success"] = (
            previous_info.get("date_last_success") or info["date_last_success"]
        )

    _LOGGER.debug(
        "[HA Monitoring Backup] RÉSULTAT API NATIVE -> last_run=%s | last_success=%s | "
        "next_schedule=%s | size=%s | is_ok=%s | failure=%s",
        info["date_last_run"],
        info["date_last_success"],
        info["date_next_schedule"],
        info["size"],
        info["is_ok"],
        info["failure"],
    )
    return info
