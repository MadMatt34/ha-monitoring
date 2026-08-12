"""Gestion des erreurs de traces pour les automatisations et scripts."""

from collections.abc import Iterable, Mapping
from datetime import datetime
import logging
from typing import TypedDict, cast

from homeassistant.components.trace.util import (
    async_get_trace,
    async_list_traces,
)
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


class TraceThisStateData(TypedDict, total=False):
    """État de l'entité enregistré au moment du trigger."""

    entity_id: str
    attributes: dict[str, object]


class TraceChangedVariablesData(TypedDict, total=False):
    """Variables enregistrées au moment du trigger."""

    this: TraceThisStateData


class TraceTriggerEntry(TypedDict, total=False):
    """Entrée d'une trace de trigger."""

    changed_variables: TraceChangedVariablesData


class TraceConfigData(TypedDict, total=False):
    """Configuration enregistrée dans une trace."""

    alias: str
    id: str


class TraceExtendedData(TypedDict, total=False):
    """Structure utile de l'extended_dict d'une trace HA."""

    domain: str
    item_id: str
    run_id: str
    timestamp: TraceTimestampData
    error: str
    config: TraceConfigData
    trace: dict[str, list[TraceTriggerEntry]]


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


def _get_trace_timestamp(
    trace: TraceShortData,
) -> datetime | None:
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
    return {
        value.strip()
        for value in (excluded or ())
        if value and value.strip()
    }


def _get_trace_alias(
    trace: TraceExtendedData,
    fallback_entity_id: str,
) -> str:
    """Retourne le nom de l'automatisation/script depuis la trace."""
    config = trace.get("config")

    if config is not None:
        alias = config.get("alias")

        if isinstance(alias, str) and alias.strip():
            return alias.strip()

    return fallback_entity_id


def _get_trace_entity_id(
    trace: TraceExtendedData,
    fallback_entity_id: str,
) -> str:
    """Retourne l'entity_id réel enregistré dans la trace."""
    trace_data = trace.get("trace")

    if not trace_data:
        return fallback_entity_id

    trigger_entries = trace_data.get("trigger")

    if not trigger_entries:
        return fallback_entity_id

    for trigger_entry in trigger_entries:
        changed_variables = trigger_entry.get("changed_variables")

        if not changed_variables:
            continue

        this_state = changed_variables.get("this")

        if not this_state:
            continue

        entity_id = this_state.get("entity_id")

        if isinstance(entity_id, str) and entity_id:
            return entity_id

    return fallback_entity_id


async def _get_error_trace_details(
    hass: HomeAssistant,
    trace: TraceShortData,
) -> tuple[str, str]:
    """Récupère le nom et l'entity_id réels d'une trace en erreur."""
    domain = trace["domain"]
    item_id = trace["item_id"]
    run_id = trace["run_id"]

    fallback_entity_id = f"{domain}.{item_id}"

    try:
        extended_raw = await async_get_trace(
            hass,
            fallback_entity_id,
            run_id,
        )
    except KeyError:
        # La trace peut disparaître entre async_list_traces() et
        # async_get_trace() (nouvelle exécution, limite du buffer, etc.).
        _LOGGER.debug(
            "[HA Monitoring] Trace %s / %s indisponible lors de "
            "la récupération détaillée.",
            fallback_entity_id,
            run_id,
        )
        return fallback_entity_id, fallback_entity_id

    extended_trace = cast(
        TraceExtendedData,
        extended_raw,
    )

    entity_id = _get_trace_entity_id(
        extended_trace,
        fallback_entity_id,
    )

    name = _get_trace_alias(
        extended_trace,
        entity_id,
    )

    return name, entity_id


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

    traces = [
        cast(TraceShortData, trace)
        for trace in traces_raw
        if isinstance(trace, dict)
    ]

    # Une seule trace de référence par automation/script :
    # la dernière exécution réelle.
    latest_traces: dict[str, TraceShortData] = {}

    for trace in traces:
        # Les traces not_triggered ne sont pas des exécutions.
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

    for fallback_entity_id, trace in latest_traces.items():
        error = trace.get("error")

        # Une seule règle détermine la présence dans le capteur :
        # la dernière exécution réelle contient-elle une erreur ?
        if not isinstance(error, str) or not error.strip():
            continue

        item_id = trace.get("item_id")

        if not item_id:
            continue

        if (
            fallback_entity_id in excluded_set
            or item_id in excluded_set
        ):
            continue

        name, entity_id = await _get_error_trace_details(
            hass,
            trace,
        )

        if (
            entity_id in excluded_set
            or name in excluded_set
        ):
            continue

        timestamp = _get_trace_timestamp(trace)

        if timestamp is None:
            formatted_date = "Inconnu"

            _LOGGER.debug(
                "[HA Monitoring] Trace en erreur sans timestamp : %s",
                fallback_entity_id,
            )
        else:
            formatted_date = format_date_local(timestamp)

        errors.append(
            {
                "name": name,
                "entity_id": entity_id,
                "date": formatted_date,
                "error": error.strip(),
            }
        )

        _LOGGER.debug(
            "[HA Monitoring] Erreur détectée sur %s (%s) : %s",
            name,
            formatted_date,
            error.strip(),
        )

    return errors
