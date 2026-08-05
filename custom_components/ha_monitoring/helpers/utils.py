"""Utilitaires généraux et formateurs pour HA Monitoring."""

from datetime import datetime
import logging
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components

def format_date_local(val) -> str | None:
    """Convertit un datetime ou un timestamp au format ISO local."""
    if val is None or val == "":
        return None

    dt_obj = None
    if isinstance(val, datetime):
        dt_obj = val
    elif isinstance(val, (int, float)):
        try:
            dt_obj = dt_util.utc_from_timestamp(val)
        except Exception:
            pass
    elif isinstance(val, str):
        dt_obj = dt_util.parse_datetime(val)
        if not dt_obj:
            return val

    if dt_obj:
        if dt_obj.tzinfo is None:
            dt_obj = dt_util.as_utc(dt_obj)
        return dt_util.as_local(dt_obj).isoformat()

    return str(val)

def format_size(size_val) -> str | None:
    """Formate une taille en octets vers Mo/Go."""
    if size_val is None:
        return None

    if isinstance(size_val, (int, float)):
        if size_val > 10240:
            mb = size_val / (1024 * 1024)
        else:
            mb = float(size_val)

        if mb >= 1024:
            return f"{round(mb / 1024, 2)} Go"
        return f"{round(mb, 2)} Mo"

    return str(size_val)