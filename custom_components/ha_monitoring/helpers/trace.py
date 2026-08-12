"""Gestion des erreurs de traces pour les automatisations et scripts."""

from collections.abc import Iterable
from datetime import datetime
import logging
from typing import TypedDict, cast

from homeassistant.components.trace.util import async_list_traces
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..types import TraceErrorData
from .utils import format_date_local

_LOGGER = logging.getLogger(__name__)


class TraceTimestampData(TypedDict):
    """Timestamp d'une trace HA."""

    start: datetime | str | None
    finish: datetime | str | None


class TraceShortData(TypedDict, total=False):
    """Structure courte d'une trace HA."""

    run_id: str
    state: str
    script_execution: str | None
    timestamp: TraceTimestampData
    domain: str
    item_id: str
    not_triggered: bool
    error: str


def _parse_trace_datetime(
    value: datetime | str | None,
) -> datetime | None:
    """Convertit un timestamp de trace HA en datetime UTC."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return dt_util.as_utc(value)

    parsed = dt_util.parse_datetime(value)

    if parsed is None:
        return None

    return dt_util.as_utc(parsed)


def _get_trace_timestamp(trace: TraceShortData) -> datetime | None:
    """Retourne le timestamp de fin d'une trace, ou son début."""
    timestamp = trace.get("timestamp")

    if not timestamp:
        return None

    finish = _parse_trace_datetime(timestamp.get("finish"))

    if finish is not None:
        return finish

    return _parse_trace_datetime(timestamp.get("start"))


def _is_latest_trace(
    candidate: TraceShortData,
    current: TraceShortData,
) -> bool:
    """Retourne True si candidate est plus récente que current."""
    candidate_timestamp = _get_trace_timestamp(candidate)
    current_timestamp = _get_trace_timestamp(current)

    if candidate_timestamp is None:
        return False

    if current_timestamp is None:
        return True

    return candidate_timestamp > current_timestamp


def _normalize_exclusions(
    excluded: Iterable[str] | None,
) -> set[str]:
    """Normalise les exclusions."""
    return {value.strip() for value in (excluded or ()) if value and value.strip()}


async def get_trace_errors(
    hass: HomeAssistant,
    domain: str,
    excluded: list[str] | None = None,
) -> list[TraceErrorData]:
    """Retourne les scripts/automatisations dont la dernière exécution a rencontré une erreur."""
    if domain not in ("automation", "script"):
        _LOGGER.warning(
            "[HA Monitoring] Domaine de trace non supporté : %s",
            domain,
        )
        return []

    excluded_set = _normalize_exclusions(excluded)

    traces_raw = await async_list_traces(
        hass,
        domain,
        None,
    )

    if not traces_raw:
        return []

    # async_list_traces() retourne des dictionnaires issus de
    # BaseTrace.as_short_dict(). Le contrat de cette API interne HA est
    # précisément documenté par le modèle TraceShort. On convertit ici
    # uniquement à la frontière avec l'API interne.
    traces = [cast(TraceShortData, trace) for trace in traces_raw if isinstance(trace, dict)]

    # On conserve uniquement la dernière exécution réelle de chaque
    # automation/script. Les traces "not_triggered" sont explicitement
    # ignorées : elles ne constituent pas une exécution du script.
    latest_traces: dict[str, TraceShortData] = {}

    for trace in traces:
        if trace.get("not_triggered") is True:
            continue

        item_id = trace.get("item_id")

        if not item_id:
            continue

        entity_id = f"{domain}.{item_id}"

        current = latest_traces.get(entity_id)

        if current is None or _is_latest_trace(trace, current):
            latest_traces[entity_id] = trace

    errors: list[TraceErrorData] = []

    for entity_id, trace in latest_traces.items():
        error = trace.get("error")

        # C'est volontairement la seule condition déterminant si
        # l'automation/script doit apparaître dans le capteur.
        #
        # Peu importe le résultat final de l'exécution :
        # si une étape a généré une erreur, le champ "error" est présent.
        if not isinstance(error, str) or not error.strip():
            continue

        item_id = trace["item_id"]

        # Les exclusions sont évaluées sur l'entity_id et l'item_id.
        # Le nom convivial est évalué ensuite.
        if entity_id in excluded_set or item_id in excluded_set:
            continue

        state = hass.states.get(entity_id)

        if state is not None:
            friendly_name = state.attributes.get("friendly_name") or state.name or entity_id
        else:
            friendly_name = entity_id

        if friendly_name in excluded_set:
            continue

        timestamp = _get_trace_timestamp(trace)

        if timestamp is None:
            _LOGGER.debug(
                "[HA Monitoring] Trace en erreur sans timestamp pour %s",
                entity_id,
            )
            formatted_date = "Inconnu"
        else:
            formatted_date = format_date_local(timestamp)

        errors.append(
            {
                "name": friendly_name,
                "entity_id": entity_id,
                "date": formatted_date,
                "error": error.strip(),
            }
        )

        _LOGGER.debug(
            "[HA Monitoring] Erreur détectée sur %s (%s) : %s",
            entity_id,
            formatted_date,
            error,
        )

    return errors
