"""Gestionnaire d'inspection des traces pour automatisations et scripts."""

from collections import deque
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import format_date_local

_LOGGER = logging.getLogger("custom_components.ha_monitoring")


def _unwrap_traces(val: Any) -> list[Any]:
    """Déballe récursivement les conteneurs (TraceBuckets, dicts, listes) pour isoler les instances de trace."""
    unwrapped = []
    if val is None:
        return unwrapped

    if hasattr(val, "runs"):
        runs_attr = getattr(val, "runs")
        unwrapped.extend(_unwrap_traces(runs_attr))
    elif isinstance(val, (list, deque, set, tuple)):
        for item in val:
            unwrapped.extend(_unwrap_traces(item))
    elif isinstance(val, dict):
        for sub_val in val.values():
            unwrapped.extend(_unwrap_traces(sub_val))
    else:
        unwrapped.append(val)

    return unwrapped


def extract_trace_error(obj: Any, depth: int = 0) -> str | None:
    """Extrait l'erreur d'une trace HA (ActionTrace / RestoredTrace / dict) en ignorant les statuts 'aborted'."""
    if obj is None or depth > 6:
        return None

    # 1. Exception Python directe
    if isinstance(obj, Exception):
        return str(obj)

    # 2. Dictionnaire ou objet convertible via as_dict()
    t_dict = None
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
        # Ignorer si le statut d'exécution est 'aborted'
        script_exec = t_dict.get("script_execution") or t_dict.get("state")
        if script_exec == "aborted":
            return None

        # Recherche directe dans le dictionnaire
        for key in ("error", "exception", "_error", "_exception"):
            val = t_dict.get(key)
            if val is not None and not callable(val):
                err_str = str(val).strip()
                if err_str and err_str != "None":
                    return err_str

        # Examen des étapes dans trace
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

    # 3. Attributs directs sur l'objet Python
    script_exec = getattr(obj, "_script_execution", None) or getattr(obj, "script_execution", None)
    state_val = getattr(obj, "_state", None) or getattr(obj, "state", None)

    if script_exec == "aborted" or state_val == "aborted":
        return None

    for attr in ("_error", "error", "_exception", "exception"):
        val = getattr(obj, attr, None)
        if val is not None and not callable(val):
            err_str = str(val).strip()
            if err_str and err_str != "None":
                return err_str

    steps = getattr(obj, "_trace", None)
    if isinstance(steps, dict):
        for step_runs in steps.values():
            runs_list = list(step_runs) if isinstance(step_runs, (list, deque, set, tuple)) else [step_runs]
            for run in reversed(runs_list):
                if isinstance(run, dict):
                    err = run.get("error") or run.get("exception")
                    if err and str(err).strip() and str(err) != "None":
                        return str(err)
                elif hasattr(run, "as_dict"):
                    try:
                        rd = run.as_dict()
                        if isinstance(rd, dict):
                            err = rd.get("error") or rd.get("exception")
                            if err and str(err).strip() and str(err) != "None":
                                return str(err)
                    except Exception:
                        pass

    if script_exec in ("failed", "error", "failed_before_steps"):
        return f"Échec d'exécution (statut: {script_exec})"
    if state_val in ("failed", "error"):
        return f"Échec d'exécution (état: {state_val})"

    return None


def extract_trace_timestamp(trace: Any, hass: HomeAssistant, entity_id: str) -> Any:
    """Extrait la date/heure d'exécution de la trace ou de l'entité."""
    # 1. Attributs directes de la trace (ActionTrace / RestoredTrace)
    for attr in ("timestamp_start", "timestamp_finish", "start_time", "finish_time"):
        val = getattr(trace, attr, None)
        if val:
            return val

    # 2. Dictionnaire timestamp internal à HA
    ts_dict = getattr(trace, "_timestamp", None) or getattr(trace, "timestamp", None)
    if not ts_dict and hasattr(trace, "as_dict"):
        try:
            td = trace.as_dict()
            if isinstance(td, dict):
                ts_dict = td.get("timestamp")
        except Exception:
            pass

    if isinstance(ts_dict, dict):
        val = ts_dict.get("start") or ts_dict.get("finish")
        if val:
            return val

    # 3. Repli sur les attributs de l'entité dans Home Assistant (ex: last_triggered)
    state = hass.states.get(entity_id)
    if state:
        last_triggered = state.attributes.get("last_triggered")
        if last_triggered:
            return last_triggered
        return state.last_updated

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
        if entry.domain == target_domain:
            if (
                entry.unique_id == key_id
                or entry.entity_id == prefixed_key
                or entry.entity_id == key_id
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
        domain = None
        item_id = None

        if isinstance(key, tuple) and len(key) >= 2:
            domain, item_id = str(key[0]), str(key[1])
        elif isinstance(key, str):
            if "." in key:
                domain, item_id = key.split(".", 1)
            else:
                domain, item_id = key, key

        if domain and item_id:
            unwrapped_list = _unwrap_traces(val)
            for trace_obj in unwrapped_list:
                items.append((domain, item_id, trace_obj))

    return items


def get_trace_errors(hass: HomeAssistant, domain: str, excluded: list) -> list[dict[str, Any]]:
    """Récupère les erreurs dans les traces d'automatisations ou de scripts."""
    trace_data = hass.data.get("trace", {})
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain

    _LOGGER.warning(
        "[HA Monitoring] SCAN TRACES pour '%s' (cible: '%s').",
        domain,
        target_domain,
    )

    if not trace_data:
        _LOGGER.warning("[HA Monitoring] Aucune clé trouvée dans hass.data['trace']")
        return []

    all_traces = _flatten_trace_data(trace_data)

    domain_traces: dict[str, list[Any]] = {}
    for dom, item_id, trace_obj in all_traces:
        obj_dom = getattr(trace_obj, "domain", None) or dom
        if obj_dom == target_domain or dom == target_domain or dom == domain:
            if item_id not in domain_traces:
                domain_traces[item_id] = []
            domain_traces[item_id].append(trace_obj)

    ent_reg = er.async_get(hass)
    failed = []

    for item_id, trace_list in domain_traces.items():
        target_trace = None
        error_msg = None

        for trace in reversed(trace_list):
            extracted_err = extract_trace_error(trace)
            if extracted_err:
                target_trace = trace
                error_msg = extracted_err
                break

        if not target_trace or not error_msg:
            continue

        entity_id = resolve_trace_entity_id(hass, target_domain, item_id, ent_reg)

        if entity_id in excluded or item_id in excluded:
            continue

        state = hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else entity_id
        if friendly_name in excluded:
            continue

        # Extraction de la date de dernière exécution de la trace
        error_time = extract_trace_timestamp(target_trace, hass, entity_id)
        formatted_date = format_date_local(error_time)

        item = {
            "name": friendly_name,
            "entity_id": entity_id,
            "date": formatted_date,
            "error": str(error_msg),
        }

        if not any(f["entity_id"] == entity_id for f in failed):
            _LOGGER.warning(
                "[HA Monitoring] ERREUR TROUVÉE sur %s (%s): %s",
                entity_id,
                formatted_date,
                error_msg,
            )
            failed.append(item)

    if not failed:
        _LOGGER.warning(
            "[HA Monitoring] Bilan pour '%s' : 0 erreur détectée sur %d élément(s) analysé(s).",
            target_domain,
            len(domain_traces),
        )

    return failed