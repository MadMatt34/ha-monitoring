"""Utilitaires généraux pour HA Monitoring."""

from datetime import datetime

from homeassistant.util import dt as dt_util


def format_date_local(
    value: datetime | str | None,
) -> str | None:
    """Convertit une date vers une chaîne ISO locale."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        dt_obj = value
    else:
        dt_obj = dt_util.parse_datetime(value)

        if dt_obj is None:
            return value

    if dt_obj.tzinfo is None:
        dt_obj = dt_util.as_utc(dt_obj)

    return dt_util.as_local(dt_obj).isoformat()
