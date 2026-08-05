"""Utilitaires généraux et formateurs pour HA Monitoring."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger("custom_components.ha_monitoring.utils")


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


def format_date_local(val: Any) -> str | None:
    """Convertit un datetime, un timestamp ou une chaîne ISO au format local ISO."""
    if val in (None, ""):
        return None

    dt_obj: datetime | None = None

    if isinstance(val, datetime):
        dt_obj = val
    elif isinstance(val, (int, float)):
        try:
            dt_obj = datetime.fromtimestamp(val, tz=dt_util.UTC)
        except (ValueError, OverflowError, OSError):
            pass
    elif isinstance(val, str):
        dt_obj = dt_util.parse_datetime(val)
        if dt_obj is None:
            return val

    if dt_obj:
        if dt_obj.tzinfo is None:
            dt_obj = dt_util.as_utc(dt_obj)
        return dt_util.as_local(dt_obj).isoformat()

    return str(val)


def format_size(size_val: Any) -> str | None:
    """Formate une taille (octets ou Mo) vers une chaîne lisible en Mo/Go."""
    if size_val is None:
        return None

    # Tente de convertir une chaîne numérique en float si nécessaire
    if isinstance(size_val, str):
        try:
            size_val = float(size_val)
        except ValueError:
            return size_val

    if isinstance(size_val, (int, float)):
        # Si la valeur est > 10240, on considère qu'elle est fournie en octets
        mb = size_val / (1024 * 1024) if size_val > 10240 else float(size_val)

        if mb >= 1024:
            return f"{mb / 1024:.2f} Go"
        return f"{mb:.2f} Mo"

    return str(size_val)