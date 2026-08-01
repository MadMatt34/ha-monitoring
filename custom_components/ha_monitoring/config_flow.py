"""Config Flow et Options Flow pour l'intégration HA Monitoring."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def get_schema(current_value: int = DEFAULT_SCAN_INTERVAL):
    """Construit le schéma de formulaire avec un champ texte pour l'intervalle."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=str(current_value),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


class HAMonitoringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux d'installation initiale via l'interface."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Formulaire d'ajout de l'intégration."""
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            try:
                interval = int(user_input[CONF_SCAN_INTERVAL])
                if interval < 5:
                    errors[CONF_SCAN_INTERVAL] = "invalid_interval"
                else:
                    return self.async_create_entry(
                        title="HA Monitoring",
                        data={},
                        options={CONF_SCAN_INTERVAL: interval},
                    )
            except ValueError:
                errors[CONF_SCAN_INTERVAL] = "invalid_number"

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Renoie le gestionnaire d'options."""
        return HAMonitoringOptionsFlowHandler(config_entry)


class HAMonitoringOptionsFlowHandler(config_entries.OptionsFlow):
    """Flux de modification des options (bouton CONFIGURE / CONFIGURER)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Formulaire d'édition de l'intervalle."""
        errors = {}
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        if user_input is not None:
            try:
                interval = int(user_input[CONF_SCAN_INTERVAL])
                if interval < 5:
                    errors[CONF_SCAN_INTERVAL] = "invalid_interval"
                else:
                    return self.async_create_entry(
                        title="",
                        data={CONF_SCAN_INTERVAL: interval},
                    )
            except ValueError:
                errors[CONF_SCAN_INTERVAL] = "invalid_number"

        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(current_interval),
            errors=errors,
        )
