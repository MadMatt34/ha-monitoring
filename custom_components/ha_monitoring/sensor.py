"""Capteurs HA Monitoring pour surveiller add-ons, intégrations, automations et scripts."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.hassio import HASSIO_DATA

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    ICON_ADDONS,
    ICON_INTEGRATIONS,
    ICON_AUTOMATIONS,
    ICON_SCRIPTS,
    UNIQUE_ID_ADDONS,
    UNIQUE_ID_INTEGRATIONS,
    UNIQUE_ID_AUTOMATIONS,
    UNIQUE_ID_SCRIPTS,
    TRANSLATION_KEY_ADDONS,
    TRANSLATION_KEY_INTEGRATIONS,
    TRANSLATION_KEY_AUTOMATIONS,
    TRANSLATION_KEY_SCRIPTS,
    ATTR_ADDONS_EN_ERREUR,
    ATTR_INTEGRATIONS_EN_ERREUR,
    ATTR_AUTOMATIONS_EN_ERREUR,
    ATTR_SCRIPTS_EN_ERREUR,
    ATTR_TOTAL_EN_ERREUR,
    INTEGRATION_ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Ajoute l'ensemble des capteurs de surveillance HA Monitoring."""
    async_add_entities([
        AddonErrorSensor(hass),
        IntegrationErrorSensor(hass),
        TraceErrorSensor(
            hass,
            domain="automation",
            unique_id=UNIQUE_ID_AUTOMATIONS,
            translation_key=TRANSLATION_KEY_AUTOMATIONS,
            icon=ICON_AUTOMATIONS,
            attr_key=ATTR_AUTOMATIONS_EN_ERREUR,
        ),
        TraceErrorSensor(
            hass,
            domain="script",
            unique_id=UNIQUE_ID_SCRIPTS,
            translation_key=TRANSLATION_KEY_SCRIPTS,
            icon=ICON_SCRIPTS,
            attr_key=ATTR_SCRIPTS_EN_ERREUR,
        ),
    ], True)


class AddonErrorSensor(SensorEntity):
    """Capteur indiquant le nombre et la liste des add-ons en erreur."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_ADDONS
    _attr_unique_id = UNIQUE_ID_ADDONS
    _attr_icon = ICON_ADDONS

    def __init__(self, hass):
        self._hass = hass
        self._state = 0
        self._failed_addons = []

    @property
    def state(self):
        """Retourne le nombre d'add-ons en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne les attributs du capteur."""
        return {
            ATTR_ADDONS_EN_ERREUR: self._failed_addons,
            ATTR_TOTAL_EN_ERREUR: len(self._failed_addons)
        }

    async def async_update(self):
        """Récupère les données depuis le Supervisor."""
        if "hassio" not in self._hass.config.components:
            _LOGGER.warning("Supervisor non disponible sur ce système.")
            return

        try:
            client = self._hass.data.get(HASSIO_DATA)
            if not client:
                return

            addons_info = await client.get_addons_info()
            addons = addons_info.get("addons", [])

            failed = []
            for addon in addons:
                state = addon.get("state")
                boot = addon.get("boot")
                watchdog = addon.get("watchdog", False)

                is_monitored = watchdog or (boot == "auto")
                is_stopped = state in ["stopped", "unknown"]

                if is_monitored and is_stopped:
                    failed.append(addon.get("name", addon.get("slug")))

            self._failed_addons = failed
            self._state = len(failed)

        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring (Add-ons) : %s", err)


class IntegrationErrorSensor(SensorEntity):
    """Capteur indiquant le nombre et la liste des intégrations en erreur."""

    _attr_has_entity_name = True
    _attr_translation_key = TRANSLATION_KEY_INTEGRATIONS
    _attr_unique_id = UNIQUE_ID_INTEGRATIONS
    _attr_icon = ICON_INTEGRATIONS

    def __init__(self, hass):
        self._hass = hass
        self._state = 0
        self._failed_integrations = []

    @property
    def state(self):
        """Retourne le nombre d'intégrations en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne les attributs du capteur."""
        return {
            ATTR_INTEGRATIONS_EN_ERREUR: self._failed_integrations,
            ATTR_TOTAL_EN_ERREUR: len(self._failed_integrations)
        }

    async def async_update(self):
        """Récupère les intégrations en erreur via config_entries."""
        try:
            failed = []
            entries = self._hass.config_entries.async_entries()

            for entry in entries:
                if entry.state in INTEGRATION_ERROR_STATES:
                    name = entry.title if entry.title else entry.domain
                    failed.append(name)

            self._failed_integrations = failed
            self._state = len(failed)

        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring (Intégrations) : %s", err)


class TraceErrorSensor(SensorEntity):
    """Capteur générique pour vérifier les erreurs d'exécution via le gestionnaire de Traces (Automations / Scripts)."""

    _attr_has_entity_name = True

    def __init__(self, hass, domain, unique_id, translation_key, icon, attr_key):
        self._hass = hass
        self._domain = domain
        self._attr_unique_id = unique_id
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_key = attr_key
        self._state = 0
        self._failed_items = []

    @property
    def state(self):
        """Retourne le nombre d'éléments en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne la liste et le total en attributs."""
        return {
            self._attr_key: self._failed_items,
            ATTR_TOTAL_EN_ERREUR: len(self._failed_items)
        }

    async def async_update(self):
        """Analyse le store de traces pour repérer la dernière exécution de chaque entité."""
        trace_data = self._hass.data.get("trace")
        if not trace_data:
            self._state = 0
            self._failed_items = []
            return

        failed = []
        try:
            for key, traces in list(trace_data.items()):
                if not (key.startswith(f"{self._domain}.") or key.startswith(f"{self._domain} ")):
                    continue

                if not traces:
                    continue

                try:
                    trace_list = list(traces.values()) if isinstance(traces, dict) else list(traces)
                    if not trace_list:
                        continue
                    latest_trace = trace_list[-1]
                except Exception:
                    continue

                error = None
                if hasattr(latest_trace, "as_dict"):
                    error = latest_trace.as_dict().get("error")
                elif isinstance(latest_trace, dict):
                    error = latest_trace.get("error")

                if error:
                    entity_id = key if key.startswith(f"{self._domain}.") else None
                    friendly_name = None

                    if entity_id:
                        state = self._hass.states.get(entity_id)
                        if state:
                            friendly_name = state.attributes.get("friendly_name") or entity_id

                    if not friendly_name:
                        for state in self._hass.states.async_all(self._domain):
                            if state.attributes.get("id") and str(state.attributes.get("id")) in key:
                                friendly_name = state.attributes.get("friendly_name") or state.entity_id
                                break

                    friendly_name = friendly_name or key
                    if friendly_name not in failed:
                        failed.append(friendly_name)

            self._failed_items = failed
            self._state = len(failed)

        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring (%s) : %s", self._domain, err)
