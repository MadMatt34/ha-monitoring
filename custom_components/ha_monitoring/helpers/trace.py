"""Gestionnaire d'inspection des traces pour automatisations et scripts."""

from collections import deque
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .utils import format_date_local

_LOGGER = logging.getLogger("custom_components.ha_monitoring.trace")


def _unwrap_traces(val: Any) -> list[Any]:
    """Déballe récursivement les conteneurs (TraceBuckets, deques, listes)."""
    if val is None:
        return []

    unwrapped = []
    if hasattr(val, "runs"):
        unwrapped.extend(_unwrap_traces(getattr(val, "runs")))
    elif isinstance(val, (list, deque, set, tuple)):
        for item in val:
            unwrapped.extend(_unwrap_traces(item))
    elif isinstance(val, dict):
        if any(k in val for k in ("trace", "script_execution", "run_id", "timestamp", "error", "config")):
            unwrapped.append(val)
        else:
            for sub_val in val.values():
                unwrapped.extend(_unwrap_traces(sub_val))
    else:
        unwrapped.append(val)

    return unwrapped


def _get_raw_trace_timestamp(trace: Any) -> Any:
    """Extrait l'horodatage brut d'une trace (objet ou dict)."""
    if trace is None:
        return None

    for attr in ("timestamp_start", "start_time", "timestamp_finish", "finish_time"):
        if isinstance(trace, dict):
            val = trace.get(attr)
        else:
            val = getattr(trace, attr, None)
        if val:
            return val

    if isinstance(trace, dict):
        ts_info = trace.get("timestamp")
    else:
        ts_info = getattr(trace, "_timestamp", None) or getattr(trace, "timestamp", None)

    if ts_info:
        if isinstance(ts_info, dict):
            val = ts_info.get("start") or ts_info.get("finish")
            if val:
                return val
        else:
            val = getattr(ts_info, "start", None) or getattr(ts_info, "finish", None)
            if val:
                return val

    if hasattr(trace, "as_dict"):
        try:
            t_dict = trace.as_dict()
            if isinstance(t_dict, dict):
                ts_info = t_dict.get("timestamp")
                if isinstance(ts_info, dict):
                    val = ts_info.get("start") or ts_info.get("finish")
                    if val:
                        return val
        except Exception:
            pass

    return None


def _parse_timestamp(val: Any) -> datetime | None:
    """Convertit un horodatage brut en objet datetime UTC comparable."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return dt_util.as_utc(val)
    if isinstance(val, str):
        parsed = dt_util.parse_datetime(val)
        if parsed:
            return dt_util.as_utc(parsed)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=dt_util.UTC)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def extract_trace_timestamp(trace: Any, hass: HomeAssistant, entity_id: str) -> Any:
    """Extrait la date/heure d'exécution de la trace ou bascule sur l'état de l'entité."""
    raw_ts = _get_raw_trace_timestamp(trace)
    if raw_ts:
        return raw_ts

    state = hass.states.get(entity_id)
    if state:
        return state.attributes.get("last_triggered") or state.last_updated

    return None


def extract_trace_error(obj: Any, depth: int = 0) -> str | None:
    """Extrait l'erreur d'une trace HA en ignorant les statuts 'aborted'."""
    if obj is None or depth > 6:
        return None

    if isinstance(obj, Exception):
        return str(obj)

    t_dict: dict[str, Any] | None = None
    if hasattr(obj, "as_dict"):
        try:
            d = obj.as_dict()
            if isinstance(d, dict):
                t_dict = d
        except Exception:
            pass
    elif isinstance(obj, dict):
        t_dict = obj

    if t_dict is not None:
        script_exec = t_dict.get("script_execution")
        if script_exec == "aborted":
            return None

        for key in ("error", "exception", "_error", "_exception"):
            val = t_dict.get(key)
            if val is not None and not callable(val):
                err_str = str(val).strip()
                if err_str and err_str != "None":
                    return err_str

        trace_steps = t_dict.get("trace")
        if isinstance(trace_steps, dict):
            for step_runs in trace_steps.values():
                runs_list = list(step_runs) if isinstance(step_runs, (list, deque, set, tuple)) else [step_runs]
                for run in reversed(runs_list):
                    if isinstance(run, dict):
                        for k in ("error", "exception"):
                            v = run.get(k)
                            if v is not None and str(v).strip() and str(v) != "None":
                                return str(v)
                        res = run.get("result")
                        if isinstance(res, dict):
                            err = res.get("error") or res.get("exception")
                            if err and str(err).strip() and str(err) != "None":
                                return str(err)

        if script_exec in ("failed", "error", "failed_before_steps"):
            return f"Échec d'exécution (statut: {script_exec})"

    script_exec_obj = getattr(obj, "_script_execution", None) or getattr(obj, "script_execution", None)
    state_obj = getattr(obj, "_state", None) or getattr(obj, "state", None)

    if script_exec_obj == "aborted" or state_obj == "aborted":
        return None

    for attr in ("_error", "error", "_exception", "exception"):
        val = getattr(obj, attr, None)
        if val is not None and not callable(val):
            err_str = str(val).strip()
            if err_str and err_str != "None":
                return err_str

    steps_obj = getattr(obj, "_trace", None)
    if isinstance(steps_obj, dict):
        for step_runs in steps_obj.values():
            runs_list = list(step_runs) if isinstance(step_runs, (list, deque, set, tuple)) else [step_runs]
            for run in reversed(runs_list):
                run_err = getattr(run, "_error", None) or getattr(run, "error", None)
                if run_err and str(run_err).strip() and str(run_err) != "None":
                    return str(run_err)

    if script_exec_obj in ("failed", "error", "failed_before_steps"):
        return f"Échec d'exécution (statut: {script_exec_obj})"

    if state_obj in ("failed", "error"):
        return f"Échec d'exécution (état: {state_obj})"

    return None


def resolve_trace_entity_id(
    hass: HomeAssistant, target_domain: str, key_id: str, ent_reg: er.EntityRegistry
) -> str:
    """Résout l'entity_id correspondant à l'ID d'une trace."""
    if key_id.startswith(f"{target_domain}."):
        if hass.states.get(key_id):
            return key_id

    prefixed_key = f"{target_domain}.{key_id}"
    if hass.states.get(prefixed_key):
        return prefixed_key

    for entry in ent_reg.entities.values():
        if entry.domain == target_domain and (
            entry.unique_id == key_id
            or entry.entity_id in (prefixed_key, key_id)
        ):
            return entry.entity_id

    for state in hass.states.async_all(target_domain):
        if state.attributes.get("id") == key_id:
            return state.entity_id

    return prefixed_key


def _flatten_trace_data(trace_data: Any) -> list[tuple[str, str, Any]]:
    """Parcourt hass.data['trace'] et extrait tous les objets de trace déballés."""
    items = []
    if not trace_data or not hasattr(trace_data, "items"):
        return items

    for key, val in trace_data.items():
        if isinstance(key, tuple) and len(key) >= 2:
            domain, item_id = str(key[0]), str(key[1])
        elif isinstance(key, str):
            if "." in key:
                domain, item_id = key.split(".", 1)
            else:
                domain, item_id = key, key
        else:
            continue

        for trace_obj in _unwrap_traces(val):
            items.append((domain, item_id, trace_obj))

    return items


def get_trace_errors(
    hass: HomeAssistant, domain: str, excluded: list[str] | None = None
) -> list[dict[str, Any]]:
    """Récupère les erreurs dans les traces d'automatisations ou de scripts."""
    excluded_list = excluded or []
    trace_data = hass.data.get("trace", {})
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain

    _LOGGER.debug("[HA Monitoring] SCAN TRACES pour '%s' (cible: '%s').", domain, target_domain)

    if not trace_data:
        _LOGGER.debug("[HA Monitoring] Aucune clé trouvée dans hass.data['trace']")
        return []

    domain_traces: dict[str, list[Any]] = {}
    for dom, item_id, trace_obj in _flatten_trace_data(trace_data):
        obj_dom = getattr(trace_obj, "domain", None) or dom
        if obj_dom == target_domain or dom == target_domain or dom == domain:
            domain_traces.setdefault(item_id, []).append(trace_obj)

    ent_reg = er.async_get(hass)
    failed = []

    for item_id, trace_list in domain_traces.items():
        def _sort_key(item_tuple: tuple[int, Any]) -> tuple[datetime, int]:
            idx, t = item_tuple
            raw_ts = _get_raw_trace_timestamp(t)
            dt_val = _parse_timestamp(raw_ts)
            if dt_val:
                return (dt_val, idx)
            return (datetime.min.replace(tzinfo=dt_util.UTC), idx)

        indexed_traces = list(enumerate(trace_list))
        sorted_indexed = sorted(indexed_traces, key=_sort_key, reverse=True)

        if not sorted_indexed:
            continue

        _, latest_trace = sorted_indexed[0]
        error_msg = extract_trace_error(latest_trace)

        if not error_msg:
            continue

        entity_id = resolve_trace_entity_id(hass, target_domain, item_id, ent_reg)
        if entity_id in excluded_list or item_id in excluded_list:
            continue

        state = hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else entity_id
        if friendly_name in excluded_list:
            continue

        error_time = extract_trace_timestamp(latest_trace, hass, entity_id)
        formatted_date = format_date_local(error_time)

        if not any(f["entity_id"] == entity_id for f in failed):
            _LOGGER.debug(
                "[HA Monitoring] ERREUR TROUVÉE sur %s (%s): %s",
                entity_id,
                formatted_date,
                error_msg,
            )
            failed.append({
                "name": friendly_name,
                "entity_id": entity_id,
                "date": formatted_date,
                "error": str(error_msg),
            })

    return failed