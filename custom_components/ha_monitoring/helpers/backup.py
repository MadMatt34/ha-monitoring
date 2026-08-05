"""Gestionnaire d'état et de planification des sauvegardes."""

from datetime import datetime, time, timedelta
import logging
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .utils import format_date_local, format_size, is_hassio_running

_LOGGER = logging.getLogger(__name__)


def calculate_next_backup(schedule_state: Any, schedule_time_obj: Any) -> datetime | None:
    """Calcule la date et l'heure de la prochaine sauvegarde."""
    try:
        state_str = str(schedule_state).split(".")[-1].lower()
        if not state_str or state_str == "never":
            return None

        now = dt_util.now()

        if isinstance(schedule_time_obj, time):
            h, m = schedule_time_obj.hour, schedule_time_obj.minute
        elif hasattr(schedule_time_obj, "hour") and hasattr(schedule_time_obj, "minute"):
            h, m = schedule_time_obj.hour, schedule_time_obj.minute
        else:
            parts = str(schedule_time_obj).split(":")
            h, m = int(parts[0]), int(parts[1])

        target_time = time(hour=h, minute=m)
        target_dt = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)

        if state_str == "daily":
            if now >= target_dt:
                target_dt += timedelta(days=1)
            return target_dt

        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        if state_str in days:
            target_day = days[state_str]
            current_day = now.weekday()

            days_ahead = target_day - current_day
            if days_ahead < 0 or (days_ahead == 0 and now >= target_dt):
                days_ahead += 7

            target_dt += timedelta(days=days_ahead)
            return target_dt

    except Exception as err:
        _LOGGER.debug("Erreur calcul prochaine sauvegarde : %s", err)

    return None

async def async_get_backup_info(hass: HomeAssistant, last_failure_reason: str | None) -> dict:
    """Interroge le gestionnaire officiel de sauvegarde (Backup Core ou Supervisor)."""
    backups_list = []
    next_scheduled = None

    if is_hassio_running(hass):
        try:
            client = hass.data.get("hassio")
            if client:
                backups_info = None
                if hasattr(client, "async_get_backups"):
                    backups_info = await client.async_get_backups()
                elif hasattr(client, "send_command"):
                    backups_info = await client.send_command("/backups", method="get")

                if isinstance(backups_info, dict):
                    if "data" in backups_info and isinstance(backups_info["data"], dict):
                        backups_list = backups_info["data"].get("backups", [])
                    elif "backups" in backups_info:
                        backups_list = backups_info.get("backups", [])
        except Exception as err:
            _LOGGER.debug("Erreur récupération sauvegardes via Hassio : %s", err)

    if "backup" in hass.data:
        try:
            backup_manager = hass.data["backup"]
            raw_backups = None

            if not backups_list:
                if hasattr(backup_manager, "async_get_backups"):
                    raw_backups = await backup_manager.async_get_backups()
                elif hasattr(backup_manager, "backups"):
                    raw_backups = backup_manager.backups

                if isinstance(raw_backups, dict):
                    for b in raw_backups.values():
                        if isinstance(b, dict):
                            backups_list.append(b)
                        else:
                            backups_list.append({
                                "slug": getattr(b, "slug", None) or getattr(b, "id", ""),
                                "name": getattr(b, "name", ""),
                                "date": getattr(b, "date", None),
                                "size": getattr(b, "size", 0),
                                "failed": getattr(b, "failed", False) or getattr(b, "status", "") == "failed",
                                "reason": getattr(b, "reason", None) or getattr(b, "error", None),
                            })

            if hasattr(backup_manager, "async_get_config") or hasattr(backup_manager, "config"):
                try:
                    cfg = await backup_manager.async_get_config() if hasattr(backup_manager, "async_get_config") else backup_manager.config
                    state, time_val = None, None

                    if isinstance(cfg, dict):
                        cb = cfg.get("create_backup", {})
                        if isinstance(cb, dict):
                            state, time_val = cb.get("state"), cb.get("time")
                    else:
                        cb = getattr(cfg, "create_backup", None)
                        if cb:
                            state = getattr(cb, "state", None)
                            time_val = getattr(cb, "time", None)
                            if hasattr(state, "value"):
                                state = state.value

                    if state and time_val:
                        next_scheduled = calculate_next_backup(state, time_val)
                except Exception as err:
                    _LOGGER.debug("Erreur async_get_config backup : %s", err)

        except Exception as err:
            _LOGGER.debug("Erreur récupération sauvegardes via Backup Core : %s", err)

    if not next_scheduled:
        ent_reg = er.async_get(hass)
        for entity_id, entity_entry in ent_reg.entities.items():
            if entity_entry.platform == "backup" and entity_entry.domain == "sensor":
                state_obj = hass.states.get(entity_id)
                if state_obj and state_obj.state not in (STATE_UNAVAILABLE, None, ""):
                    parsed_dt = dt_util.parse_datetime(state_obj.state)
                    if parsed_dt and parsed_dt > dt_util.utcnow():
                        next_scheduled = parsed_dt
                        break

    if not backups_list:
        return {
            "is_ok": False,
            "date_last_run": None,
            "date_last_success": None,
            "date_next_schedule": format_date_local(next_scheduled) if next_scheduled else "Not planned",
            "size": None,
            "failure": last_failure_reason or "No backup available",
        }

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
    is_ok = not is_failed

    failure = last_failure_reason
    if is_failed:
        failure = (
            latest_backup.get("reason")
            or latest_backup.get("error")
            or latest_backup.get("failure_reason")
            or last_failure_reason
            or "Unknown failure reason"
        )

    last_dt = get_date(latest_backup)
    date_last_run = format_date_local(last_dt) if last_dt != datetime.min.replace(tzinfo=dt_util.UTC) else format_date_local(latest_backup.get("date"))

    last_successful_dt = None
    for b in sorted_backups:
        if not b.get("failed", False) and b.get("status") != "failed":
            last_successful_dt = get_date(b)
            break

    date_last_success = (
        format_date_local(last_successful_dt)
        if last_successful_dt and last_successful_dt != datetime.min.replace(tzinfo=dt_util.UTC)
        else (date_last_run if is_ok else "Aucune")
    )

    date_next_schedule = format_date_local(next_scheduled) if next_scheduled else "Non planifiée"
    size = format_size(latest_backup.get("size"))

    return {
        "is_ok": is_ok,
        "date_last_run": date_last_run,
        "date_last_success": date_last_success,
        "date_next_schedule": date_next_schedule,
        "size": size,
        "failure": failure,
    }