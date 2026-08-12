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
from homeassistant.exceptions import HomeAssistantError
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
    """État de l'entité enregistré dans la trace."""

    entity_id: str
    attributes: dict[str, object]


class TraceChangedVariablesData(TypedDict, total=False):
    """Variables modifiées dans une étape de trace."""

    this: TraceThisStateData


class TraceElementData(TypedDict, total=False):
    """Structure d'une étape de trace."""

    path: str
    timestamp: datetime | str
    changed_variables: TraceChangedVariablesData
    error: str
    template_errors: list[str]
    child_id: dict[str, str]
    result: dict[str, object]


class TraceConfigData(TypedDict, total=False):
    """Configuration enregistrée dans une trace."""

    alias: str
    id: str


class TraceExtendedData(TypedDict, total=False):
    """Structure utile de l'extended_dict d'une trace."""

    domain: str
    item_id: str
    run_id: str
    timestamp: TraceTimestampData
    error: str
    config: TraceConfigData
    trace: dict[str, list[TraceElementData]]


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


def _get_element_timestamp(
    element: TraceElementData,
) -> datetime | None:
    """Retourne le timestamp d'une étape de trace."""
    return _parse_trace_datetime(element.get("timestamp"))


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
        changed_variables = trigger_entry.get(
            "changed_variables"
        )

        if not changed_variables:
            continue

        this_state = changed_variables.get("this")

        if not this_state:
            continue

        entity_id = this_state.get("entity_id")

        if isinstance(entity_id, str) and entity_id:
            return entity_id

    return fallback_entity_id


def _get_trace_alias(
    trace: TraceExtendedData,
    fallback_entity_id: str,
) -> str:
    """Retourne l'alias de l'automatisation/script."""
    config = trace.get("config")

    if config is not None:
        alias = config.get("alias")

        if isinstance(alias, str) and alias.strip():
            return alias.strip()

    return fallback_entity_id


def _format_template_errors(
    template_errors: list[str],
) -> str:
    """Formate les erreurs de template enregistrées dans une étape."""
    return " | ".join(
        error.strip()
        for error in template_errors
        if error and error.strip()
    )


def _get_element_error(
    element: TraceElementData,
) -> str | None:
    """Retourne l'erreur d'une étape, y compris les erreurs de template."""
    errors: list[str] = []

    error = element.get("error")

    if isinstance(error, str) and error.strip():
        errors.append(error.strip())

    template_errors = element.get("template_errors")

    if isinstance(template_errors, list):
        template_error = _format_template_errors(
            template_errors
        )

        if template_error:
            errors.append(template_error)

    if not errors:
        return None

    return " | ".join(errors)


def _get_latest_trace_error(
    trace: TraceExtendedData,
) -> tuple[str, datetime | None] | None:
    """Retourne la dernière erreur rencontrée pendant l'exécution."""
    errors: list[tuple[datetime, str]] = []

    # Erreur de l'exécution globale.
    global_error = trace.get("error")

    if isinstance(global_error, str) and global_error.strip():
        timestamp = _get_trace_timestamp(
            cast(TraceShortData, trace)
        )

        if timestamp is not None:
            errors.append(
                (
                    timestamp,
                    global_error.strip(),
                )
            )

    # Erreurs rencontrées dans les différentes étapes.
    trace_data = trace.get("trace")

    if trace_data:
        for elements in trace_data.values():
            for element in elements:
                error = _get_element_error(element)

                if error is None:
                    continue

                timestamp = _get_element_timestamp(element)

                if timestamp is None:
                    continue

                errors.append(
                    (
                        timestamp,
                        error,
                    )
                )

    if not errors:
        return None

    timestamp, error = max(
        errors,
        key=lambda item: item[0],
    )

    return error, timestamp


async def _get_error_trace_details(
    hass: HomeAssistant,
    trace: TraceShortData,
) -> (
    tuple[
        str,
        str,
        str,
        datetime | None,
    ]
    | None
):
    """Récupère les détails complets d'une exécution en erreur."""
    domain = trace.get("domain")
    item_id = trace.get("item_id")
    run_id = trace.get("run_id")

    if not domain or not item_id or not run_id:
        return None

    fallback_entity_id = f"{domain}.{item_id}"

    try:
        extended_raw = await async_get_trace(
            hass,
            fallback_entity_id,
            run_id,
        )
    except (KeyError, HomeAssistantError):
        _LOGGER.debug(
            "[HA Monitoring] Trace %s / %s indisponible "
            "lors de la récupération détaillée.",
            fallback_entity_id,
            run_id,
        )
        return None

    extended_trace = cast(
        TraceExtendedData,
        extended_raw,
    )

    error_details = _get_latest_trace_error(
        extended_trace
    )

    if error_details is None:
        return None

    error, error_timestamp = error_details

    entity_id = _get_trace_entity_id(
        extended_trace,
        fallback_entity_id,
    )

    name = _get_trace_alias(
        extended_trace,
        entity_id,
    )

    return (
        name,
        entity_id,
        error,
        error_timestamp,
    )


async def get_trace_errors(
    hass: HomeAssistant,
    domain: str,
    excluded: list[str] | None = None,
) -> list[TraceErrorData]:
    """Retourne les dernières exécutions ayant rencontré une erreur."""
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
        if isinstance(trace, Mapping)
    ]

    # Dernière exécution réelle de chaque automation/script.
    latest_traces: dict[str, TraceShortData] = {}

    for trace in traces:
        if trace.get("not_triggered") is True:
            continue

        item_id = trace.get("item_id")

        if not item_id:
            continue

        entity_id = f"{domain}.{item_id}"
        current = latest_traces.get(entity_id)

        if current is None or _is_latest_trace(
            trace,
            current,
        ):
            latest_traces[entity_id] = trace

    errors: list[TraceErrorData] = []

    # L'extended trace est nécessaire pour détecter les erreurs
    # sur les étapes, notamment continue_on_error et template_errors.
    for fallback_entity_id, trace in latest_traces.items():
        item_id = trace.get("item_id")

        if not item_id:
            continue

        if (
            fallback_entity_id in excluded_set
            or item_id in excluded_set
        ):
            continue

        details = await _get_error_trace_details(
            hass,
            trace,
        )

        # Aucune erreur dans cette exécution :
        # une ancienne erreur doit donc disparaître.
        if details is None:
            continue

        (
            name,
            entity_id,
            error,
            error_timestamp,
        ) = details

        if (
            entity_id in excluded_set
            or name in excluded_set
        ):
            continue

        formatted_date = (
            format_date_local(error_timestamp)
            if error_timestamp is not None
            else "Inconnu"
        )

        errors.append(
            {
                "name": name,
                "entity_id": entity_id,
                "date": formatted_date,
                "error": error,
            }
        )

        _LOGGER.debug(
            "[HA Monitoring] Erreur détectée sur %s (%s): %s",
            name,
            formatted_date,
            error,
        )

    return errors
