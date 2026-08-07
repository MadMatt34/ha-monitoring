"""Gestionnaire d'inspection des sauvegardes basé exclusivement sur les APIs natives HA."""

import dataclasses
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger("custom_components.ha_monitoring.backup")


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convertit de manière ultra-robuste tout objet/dataclass HA en dictionnaire (en ignorant les attributs privés)."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if not str(k).startswith("_")}

    res: dict[str, Any] = {}
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            res = obj.to_dict()
        except Exception:
            pass
    elif hasattr(obj, "as_dict") and callable(obj.as_dict):
        try:
            res = obj.as_dict()
        except Exception:
            pass
    elif dataclasses.is_dataclass(obj):
        try:
            res = dataclasses.asdict(obj)
        except Exception:
            pass
    elif hasattr(obj, "__dict__"):
        res = vars(obj)

    return {k: v for k, v in res.items() if not str(k).startswith("_")}


def _format_dt(raw_dt: Any) -> str | None:
    """Formate une date (datetime, ISO str, timestamp) au format JJ/MM/AAAA HH:MM en heure locale."""
    if not raw_dt:
        return None

    s_val = str(raw_dt).strip()
    if s_val.lower() in ("unknown", "unavailable", "blocked", "none", "null", "inconnu", ""):
        return None

    if isinstance(raw_dt, datetime):
        try:
            return dt_util.as_local(raw_dt).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return raw_dt.strftime("%d/%m/%Y %H:%M")

    if isinstance(raw_dt, (int, float)):
        try:
            return dt_util.as_local(dt_util.utc_from_timestamp(raw_dt)).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass

    try:
        parsed = dt_util.parse_datetime(s_val)
        if parsed:
            return dt_util.as_local(parsed).strftime("%d/%m/%Y %H:%M")
    except Exception:
        pass

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

    # 1. Recherche directe au niveau actuel
    for key in candidate_keys:
        if key in data and data[key] is not None:
            val = data[key]
            if isinstance(val, (datetime, str, int, float)):
                return val

    # 2. Exploration sous-niveaux (en ignorant les clés privées)
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


def _get_backup_size_bytes(b_obj: Any) -> int | None:
    """Extrait la taille en octets depuis l'attribut agents ou les champs de premier niveau."""
    agents = getattr(b_obj, "agents", None)
    if isinstance(agents, dict) and agents:
        total = 0
        found = False
        for agent in agents.values():
            sz = getattr(agent, "size", None)
            if sz is None and isinstance(agent, dict):
                sz = agent.get("size")
            if sz is not None:
                try:
                    total += int(sz)
                    found = True
                except (ValueError, TypeError):
                    pass
        if found and total > 0:
            return total

    b_dict = _to_dict(b_obj)
    sz = _find_scalar_field(b_dict, ("size", "bytes", "total_size", "file_size"))
    if sz is not None:
        try:
            return int(sz)
        except (ValueError, TypeError):
            pass
    return None


async def async_get_backup_info(
    hass: HomeAssistant, last_failure_reason: str | None = None
) -> dict[str, Any]:
    """Récupère les informations de sauvegarde via les APIs natives de Home Assistant."""
    info: dict[str, Any] = {
        "is_ok": True,
        "date_last_run": None,
        "date_last_success": None,
        "date_next_schedule": None,
        "size": None,
        "failure": last_failure_reason,
    }

    if "backup" in hass.data:
        try:
            b_data = hass.data["backup"]
            manager = getattr(b_data, "manager", b_data)

            # -----------------------------------------------------------------
            # 1. Extraction des sauvegardes existantes
            # -----------------------------------------------------------------
            backups_raw = None
            if hasattr(manager, "async_get_backups"):
                try:
                    backups_raw = await manager.async_get_backups()
                except Exception as err_m:
                    _LOGGER.warning("[HA Monitoring Backup] Appel async_get_backups() échoué: %s", err_m)

            if backups_raw is None and hasattr(manager, "backups"):
                backups_raw = manager.backups

            backup_list = _extract_backup_objects(backups_raw)

            if backup_list:
                valid_backups = []
                for b_obj in backup_list:
                    b_dict = _to_dict(b_obj)
                    d = _find_scalar_field(
                        b_dict, ("date", "created", "created_at", "timestamp", "utc_date")
                    )
                    if d:
                        sz = _get_backup_size_bytes(b_obj)
                        valid_backups.append((str(d), d, sz))

                if valid_backups:
                    valid_backups.sort(key=lambda x: x[0], reverse=True)
                    _, latest_date, latest_size = valid_backups[0]

                    info["date_last_run"] = _format_dt(latest_date)
                    info["date_last_success"] = info["date_last_run"]
                    info["size"] = _format_size_bytes(latest_size)

            # -----------------------------------------------------------------
            # 2. Extraction de la planification native (BackupConfig)
            # -----------------------------------------------------------------
            config_raw = None
            if hasattr(manager, "async_get_config"):
                try:
                    config_raw = await manager.async_get_config()
                except Exception:
                    pass
            if config_raw is None and hasattr(manager, "config"):
                config_raw = manager.config

            if config_raw:
                # Extraction directe ciblée depuis la structure BackupConfig -> BackupConfigData -> BackupSchedule
                data_obj = getattr(config_raw, "data", config_raw)
                schedule_obj = getattr(data_obj, "schedule", None) if not isinstance(data_obj, dict) else data_obj.get("schedule")

                next_dt = getattr(schedule_obj, "next_automatic_backup", None) if not isinstance(schedule_obj, dict) else (schedule_obj.get("next_automatic_backup") if schedule_obj else None)

                if next_dt:
                    info["date_next_schedule"] = _format_dt(next_dt)
                else:
                    # Fallback par balayage sécurisé anti-récursion
                    config_dict = _to_dict(config_raw)
                    next_schedule = _find_scalar_field(
                        config_dict,
                        ("next_automatic_backup", "next_backup", "next_run", "next_scheduled", "next_execution"),
                    )
                    if next_schedule:
                        info["date_next_schedule"] = _format_dt(next_schedule)

        except Exception as err:
            _LOGGER.warning("[HA Monitoring Backup] Erreur HA Core Manager: %s", err)

    if last_failure_reason:
        info["is_ok"] = False

    _LOGGER.warning(
        "[HA Monitoring Backup] RÉSULTAT API NATIVE -> "
        "last_run=%s | last_success=%s | next_schedule=%s | size=%s | is_ok=%s",
        info["date_last_run"],
        info["date_last_success"],
        info["date_next_schedule"],
        info["size"],
        info["is_ok"],
    )

    return info