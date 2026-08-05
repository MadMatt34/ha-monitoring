"""Gestionnaire d'inspection des traces pour automatisations et scripts."""

from collections import deque
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import format_date_local

_LOGGER = logging.getLogger(__name__)


def extract_trace_error(trace: Any) -> str | None:
    """Extrait l'erreur d'une trace HA à tous les niveaux."""
    if trace is None:
        return None

    # 1. Vérification via as_dict() (méthode officielle HA)
    t_dict = None
    if hasattr(trace, "as_dict"):
        try:
            t_dict = trace.as_dict()
        except Exception as err:
            _LOGGER.debug("[HA Monitoring] Erreur as_dict() sur la trace : %s", err)

    if isinstance(t_dict, dict):
        err = t_dict.get("error") or t_dict.get("exception")
        if err and str(err).strip() and str(err) != "None":
            return str(err)

        # Inspection des étapes dans le dictionnaire
        steps_dict = t_dict.get("trace")
        if isinstance(steps_dict, dict):
            for _path, step_runs in steps_dict.items():
                runs_list = list(step_runs) if isinstance(step_runs, (list, deque)) else [step_runs]
                for run in reversed(runs_list):
                    if isinstance(run, dict):
                        step_err = run.get("error") or run.get("exception")
                        if step_err and str(step_err).strip() and str(step_err) != "None":
                            return str(step_err)
                        res = run.get("result")
                        if isinstance(res, dict) and res.get("error"):
                            return str(res["error"])

    # 2. Attributs directs sur l'objet Python ActionTrace
    for attr in ("_error", "error", "_exception", "exception"):
        val = getattr(trace, attr, None)
        if val is not None and str(val).strip() and str(val) != "None":
            return str(val)

    # 3. Inspection des étapes (TraceElement)
    steps_trace = getattr(trace, "_trace", None)
    if isinstance(steps_trace, dict):
        for _path, step_runs in steps_trace.items():
            runs_list = list(step_runs) if isinstance(step_runs, (list, deque)) else [step_runs]
            for run in reversed(runs_list):
                if isinstance(run, dict):
                    step_err = run.get("error") or run.get("exception")
                    if step_err and str(step_err).strip() and str(step_err) != "None":
                        return str(step_err)
                else:
                    for attr in ("_error", "error", "_exception", "exception"):
                        val = getattr(run, attr, None)
                        if val is not None and str(val).strip() and str(val) != "None":
                            return str(val)

                    if hasattr(run, "as_dict"):
                        try:
                            run_dict = run.as_dict()
                            if isinstance(run_dict, dict):
                                step_err = run_dict.get("error") or run_dict.get("exception")
                                if step_err and str(step_err).strip() and str(step_err) != "None":
                                    return str(step_err)
                        except Exception:
                            pass

    # 4. Vérification du statut global d'exécution
    script_exec = None
    if isinstance(t_dict, dict):
        script_exec = t_dict.get("script_execution")
    if not script_exec:
        script_exec = getattr(trace, "_script_execution", None) or getattr(trace, "script_execution", None)

    if script_exec in ("failed", "aborted", "error", "failed_before_steps"):
        return f"Échec d'exécution (statut: {script_exec})"

    return None


def resolve_trace_entity_id(hass: HomeAssistant, domain: str, key: str, ent_reg: er.EntityRegistry) -> str:
    """Résout l'entity_id correspondant à une clé de trace."""
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain
    raw_id = key.split(".", 1)[-1] if "." in key else key

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

    return prefixed_key


def get_trace_errors(hass: HomeAssistant, domain: str, excluded: list) -> list[dict[str, Any]]:
    """Récupère les erreurs dans les traces d'automatisations ou de scripts."""
    trace_data = hass.data.get("trace", {})
    target_domain = domain.rstrip("s") if domain in ("scripts", "automations") else domain

    _LOGGER.debug(
        "[HA Monitoring] Analyse des traces pour '%s' (cible: '%s'). Total clés en mémoire: %d",
        domain,
        target_domain,
        len(trace_data) if hasattr(trace_data, "__len__") else 0,
    )

    if not trace_data or not hasattr(trace_data, "items"):
        return []

    ent_reg = er.async_get(hass)
    failed = []

    for raw_key, traces in list(trace_data.items()):
        key_str = raw_key[1] if isinstance(raw_key, tuple) else str(raw_key)

        if not traces:
            continue

        if isinstance(traces, (list, deque)):
            trace_list = list(traces)
        elif isinstance(traces, dict):
            trace_list = list(traces.values())
        else:
            trace_list = [traces]

        if not trace_list:
            continue

        # Inspection directe du domaine porté par la trace
        sample_trace = trace_list[-1]
        obj_domain = getattr(sample_trace, "domain", None)

        is_match = (
            key_str.startswith(f"{target_domain}.")
            or key_str.startswith(f"{domain}.")
            or obj_domain == target_domain
            or obj_domain == domain
        )

        if not is_match:
            continue

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

        entity_id = resolve_trace_entity_id(hass, target_domain, key_str, ent_reg)

        if entity_id in excluded or key_str in excluded:
            continue

        state = hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else entity_id
        if friendly_name in excluded:
            continue

        error_time = (
            getattr(target_trace, "timestamp_start", None)
            or getattr(target_trace, "start_time", None)
        )

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
            _LOGGER.debug("[HA Monitoring] Erreur détectée pour %s: %s", entity_id, error_msg)
            failed.append(item)

    return failed