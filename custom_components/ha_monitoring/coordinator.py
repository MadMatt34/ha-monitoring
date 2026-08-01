"""DataUpdateCoordinator pour HA Monitoring."""
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    DEFAULT_STARTUP_DELAY,
)

_LOGGER = logging.getLogger(__name__)


class HAMonitoringCoordinator(DataUpdateCoordinator):
    """Classe centrale de gestion des mises à jour des données."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        # On enregistre l'heure de démarrage du coordinator
        self._boot_time = dt_util.utcnow()

        # Lecture de l'intervalle de rafraîchissement depuis les options
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Récupère les données et gère le délai de temporisation au démarrage."""
        startup_delay = self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY)
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._boot_time).total_seconds()

        # Vérification de la phase de démarrage
        in_startup_phase = (
            self.hass.state != CoreState.running
            or elapsed_seconds < startup_delay
        )

        if in_startup_phase:
            remaining = max(0, int(startup_delay - elapsed_seconds))
            _LOGGER.debug(
                "Home Assistant est en phase d'initialisation. Temporisation active (%s s restantes)",
                remaining,
            )
            # Durant la temporisation, on renvoie des valeurs neutres
            return {
                "in_startup_delay": True,
                "monitoring_unavailable_entities": 0,
                "monitoring_offline_devices": 0,
                "monitoring_failed_automations": 0,
            }

        # --- Fin de la temporisation : Analyse réelle des métriques ---
        _LOGGER.debug("Fin du délai de grâce, exécution de l'analyse système.")

        # Remplacez / complétez ici avec vos fonctions de comptage
        unavailable_count = await self._async_get_unavailable_entities()
        offline_count = await self._async_get_offline_devices()

        return {
            "in_startup_delay": False,
            "monitoring_unavailable_entities": unavailable_count,
            "monitoring_offline_devices": offline_count,
        }

    async def _async_get_unavailable_entities(self) -> int:
        """Exemple : compte des entités indisponibles."""
        # Insérez votre logique de filtrage ici
        return 0

    async def _async_get_offline_devices(self) -> int:
        """Exemple : compte des appareils hors ligne."""
        # Insérez votre logique de filtrage ici
        return 0
