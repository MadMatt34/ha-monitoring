"""Capteurs HA Monitoring pour surveiller add-ons, intégrations, automations et scripts."""
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.hassio import HASSIO_DATA
from homeassistant.config_entries import ConfigEntryState

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Ajoute l'ensemble des capteurs de surveillance HA Monitoring."""
    async_add_entities([
        AddonErrorSensor(hass),
        IntegrationErrorSensor(hass),
        TraceErrorSensor(hass, domain="automation", name="Automations en erreur", unique_id="ha_monitoring_automations_in_error", icon="mdi:robot-dead"),
        TraceErrorSensor(hass, domain="script", name="Scripts en erreur", unique_id="ha_monitoring_scripts_in_error", icon="mdi:script-text-outline"),
    ], True)


class AddonErrorSensor(SensorEntity):
    """Capteur indiquant le nombre et la liste des add-ons en erreur."""

    def __init__(self, hass):
        self._hass = hass
        self._state = 0
        self._failed_addons = []
        self._attr_name = "Add-ons en erreur"
        self._attr_unique_id = "ha_monitoring_addons_in_error_sensor"
        self._attr_icon = "mdi:puzzle-alert"

    @property
    def state(self):
        """Retourne le nombre d'add-ons en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne les attributs du capteur."""
        return {
            "addons_en_erreur": self._failed_addons,
            "total_en_erreur": len(self._failed_addons)
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

    def __init__(self, hass):
        self._hass = hass
        self._state = 0
        self._failed_integrations = []
        self._attr_name = "Intégrations en erreur"
        self._attr_unique_id = "ha_monitoring_integrations_in_error_sensor"
        self._attr_icon = "mdi:alert-circle-outline"

    @property
    def state(self):
        """Retourne le nombre d'intégrations en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne les attributs du capteur."""
        return {
            "integrations_en_erreur": self._failed_integrations,
            "total_en_erreur": len(self._failed_integrations)
        }

    async def async_update(self):
        """Récupère les intégrations en erreur via config_entries."""
        try:
            failed = []
            entries = self._hass.config_entries.async_entries()

            error_states = {
                ConfigEntryState.SETUP_ERROR,
                ConfigEntryState.SETUP_RETRY,
                ConfigEntryState.MIGRATION_ERROR,
            }

            for entry in entries:
                if entry.state in error_states:
                    name = entry.title if entry.title else entry.domain
                    failed.append(name)

            self._failed_integrations = failed
            self._state = len(failed)

        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring (Intégrations) : %s", err)


class TraceErrorSensor(SensorEntity):
    """Capteur générique pour vérifier les erreurs d'exécution via le gestionnaire de Traces (Automations / Scripts)."""

    def __init__(self, hass, domain, name, unique_id, icon):
        self._hass = hass
        self._domain = domain
        self._state = 0
        self._failed_items = []
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = icon

    @property
    def state(self):
        """Retourne le nombre d'éléments en erreur."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Retourne la liste et le total en attributs."""
        attr_key = f"{self._domain}s_en_erreur"
        return {
            attr_key: self._failed_items,
            "total_en_erreur": len(self._failed_items)
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
                # Vérifie si la clé concerne le domaine (ex: "automation.xxx" ou "script.xxx")
                if not (key.startswith(f"{self._domain}.") or key.startswith(f"{self._domain} ")):
                    continue

                if not traces:
                    continue

                # Récupère la trace de la dernière exécution
                try:
                    trace_list = list(traces.values()) if isinstance(traces, dict) else list(traces)
                    if not trace_list:
                        continue
                    latest_trace = trace_list[-1]
                except Exception:
                    continue

                # Vérification de la présence d'une erreur dans la trace
                error = None
                if hasattr(latest_trace, "as_dict"):
                    error = latest_trace.as_dict().get("error")
                elif isinstance(latest_trace, dict):
                    error = latest_trace.get("error")

                if error:
                    # Résolution du nom convivial (friendly_name)
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
