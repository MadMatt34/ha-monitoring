"""Gestionnaire d'inspection des traces pour automatisations et scripts."""

from collections import deque
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import format_date_local

_LOGGER = logging.getLogger(__name__)


def extract_trace_error(trace: Any) -> str | None:
    """Extrait l'erreur d'une trace HA à tous les niveaux (objets, dictionnaires et TraceElement)."""
    if trace is None:
        return None

    # 1. Attributs directs au niveau de l'objet ActionTrace
    for attr in ("_error", "error", "_exception", "exception"):
        val = getattr(trace, attr, None)
        if val is not None and str(val).strip() and str(val) != "None":
            return str(val)

    # 2. Structure as_dict()
    t_dict = None
    if hasattr(trace, "as_dict"):
        try:
            t_dict = trace.as_dict()
        except Exception:
            t_dict = None
    elif isinstance(trace, dict):
        t_dict = trace

    if isinstance(t_dict, dict):
        err = t_dict.get("error") or t_dict.get("exception")
        if err and str(err).strip() and str(err) != "None":
            return str(err)

    # 3. Parcours des étapes d'exécution (TraceElement / Spook)
    steps_trace = None
    if isinstance(t_dict, dict) and isinstance(t_dict.get("trace"), dict):
        steps_trace = t_dict["trace"]
    else:
        steps_trace = getattr(trace, "_trace", None)

    if isinstance(steps_trace, dict):
        for _path, step_runs in steps_trace.items():
            if not isinstance(step_runs, list):
                step_runs = [step_runs]

            for run in reversed(step_runs):
                if isinstance(run, dict):
                    err = run.get("error") or run.get("exception")
                    if err and str(err).strip() and str(err) != "None":
                        return str(err)
                    res = run.get("result")
                    if isinstance(res, dict) and res.get("error"):
                        return str(res["error"])
                else:
                    # Inspection directe de l'instance TraceElement (utilisé par Spook)
                    for attr in ("_error", "error", "_exception", "exception"):
                        val = getattr(run, attr, None)
                        if val is not None and str(val).strip() and str(val) != "None":
                            return str(val)

                    if hasattr(run, "as_dict"):
                        try:
                            run_dict = run.as_dict()
                            if isinstance(run_dict, dict):
                                err = run_dict.get("error") or run_dict.get("exception")
                                if err and str(err).strip() and str(err) != "None":
                                    return str(err)
                        except Exception:
                            pass

    # 4. Statut global si l'exécution a échoué
    script_exec = None
    if isinstance(t_dict, dict):
        script_exec = t_dict.get("script_execution")
    if not script_exec:
        script_exec = getattr(trace, "_script_execution", None) or getattr(trace, "script_execution", None)

    if script_exec in ("failed", "aborted", "error"):
        return f"Échec d'exécution (statut: {script_exec})"

    return None

def resolve_trace_entity_id(hass: HomeAssistant, domain: str, key: str, ent_reg: er.EntityRegistry) -> str:
    """Résout l'entity_id correspondant à une clé de trace (ex: automation.1708...)."""
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain
    raw_id = key.split(".", 1)[-1]

    if hass.states.get(key):
        return key

    prefixed_key = f"{target_domain}.{raw_id}"
    if hass.states.get(prefixed_key):
        return prefixed_key

    for entry in ent_reg.entities.values():
        if entry.domain == target_domain and (
            entry.unique_id == raw_id
            or entry.entity_id == key
            or entry.entity_id == prefixed_key
            or entry.unique_id == key
        ):
            return entry.entity_id

    for state in hass.states.async_all(target_domain):
        if state.attributes.get("id") == raw_id:
            return state.entity_id

    return key

def get_trace_errors(hass: HomeAssistant, domain: str, excluded: list) -> list[dict[str, Any]]:
    """Récupère les erreurs dans les traces d'automatisations ou de scripts."""
    trace_data = hass.data.get("trace", {})
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain

    _LOGGER.debug(
        "[HA Monitoring] Analyse des traces pour '%s' (cible: '%s'). Total clés: %d",
        domain,
        target_domain,
        len(trace_data) if isinstance(trace_data, dict) else 0,
    )

    if not trace_data or not isinstance(trace_data, dict):
        return []

    ent_reg = er.async_get(hass)
    failed = []

    for key, traces in list(trace_data.items()):
        if not (key.startswith(f"{target_domain}.") or key.startswith(f"{domain}.")):
            continue

        if not traces:
            continue

        if isinstance(traces, dict):
            trace_list = list(traces.values())
        elif isinstance(traces, (list, deque)):
            trace_list = list(traces)
        else:
            trace_list = [traces]

        if not trace_list:
            continue

        target_trace = None
        error_msg = None

        for idx, trace in enumerate(reversed(trace_list)):
            extracted_err = extract_trace_error(trace)
            if extracted_err:
                target_trace = trace
                error_msg = extracted_err
                break

        if not target_trace or not error_msg:
            continue

        entity_id = resolve_trace_entity_id(hass, domain, key, ent_reg)

        if entity_id in excluded or key in excluded:
            continue

        state = hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else entity_id
        if friendly_name in excluded:
            continue

        error_time = getattr(target_trace, "start_time", None)
        if not error_time and hasattr(target_trace, "as_dict"):
            try:
                t_dict = target_trace.as_dict()
                ts_info = t_dict.get("timestamp", {})
                if isinstance(ts_info, dict):
                    error_time = ts_info.get("start") or ts_info.get("finish")
            except Exception:
                pass

        formatted_date = format_date_local(error_time)

        item = {
            "name": friendly_name,
            "entity_id": entity_id,
            "date": formatted_date,
            "error": str(error_msg),
        }

        if not any(f["entity_id"] == entity_id for f in failed):
            failed.append(item)

    return failed