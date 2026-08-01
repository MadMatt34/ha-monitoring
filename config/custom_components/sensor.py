"""Capteur pour surveiller les add-ons en erreur."""
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.hassio import HASSIO_DATA

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Ajoute le capteur à Home Assistant."""
    async_add_entities([AddonErrorSensor(hass)], True)

class AddonErrorSensor(SensorEntity):
    """Capteur indiquant le nombre et la liste des add-ons en erreur."""

    def __init__(self, hass):
        self._hass = hass
        self._state = 0
        self._failed_addons = []
        self._attr_name = "Add-ons en erreur"
        self._attr_unique_id = "supervisor_addons_in_error_sensor"
        self._attr_icon = "mdi:puzzle-alert"

    @property
    <li>
      **State & Attributes**
    </li>
    
    @property
    def state(self):
        """Retourne le nombre d'add-ons en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne la liste des add-ons tombés en erreur."""
        return {
            "addons_en_erreur": self._failed_addons,
            "total_en_erreur": len(self._failed_addons)
        }

    async def async_update(self):
        """Récupère les données depuis le Supervisor."""
        # Vérification si Hass.io / Supervisor est disponible
        if "hassio" not in self._hass.config.components:
            _LOGGER.warning("Supervisor non disponible sur ce système.")
            return

        try:
            # Appel de l'API interne du Supervisor via le client Hassio de HA
            client = self._hass.data.get(HASSIO_DATA)
            if not client:
                return

            addons_info = await client.get_addons_info()
            addons = addons_info.get("addons", [])

            failed = []
            for addon in addons:
                # Un add-on est considéré en erreur s'il est configuré en auto-start (boot: auto)
                # mais qu'il est arrêté (state: stopped ou unknown)
                state = addon.get("state")
                boot = addon.get("boot")
                
                if boot == "auto" and state in ["stopped", "unknown"]:
                    failed.append(addon.get("name", addon.get("slug")))

            self._failed_addons = failed
            self._state = len(failed)

        except Exception as err:
            _LOGGER.error("Erreur lors de la récupération des add-ons : %s", err)
