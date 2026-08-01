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
    CONF_OFFLINE_TIMEOUT,
    DEFAULT_OFFLINE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def get_schema(
    current_interval: int = DEFAULT_SCAN_INTERVAL,
    current_timeout: int = DEFAULT_OFFLINE_TIMEOUT,
):
    """Construit le schéma de formulaire avec champ texte pour l'intervalle et champ numérique pour le timeout."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=str(current_interval),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_OFFLINE_TIMEOUT,
                default=current_timeout,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=720,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
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
                timeout = int(user_input[CONF_OFFLINE_TIMEOUT])

                if interval < 5:
                    errors[CONF_SCAN_INTERVAL] = "invalid_interval"
                elif timeout < 1:
                    errors[CONF_OFFLINE_TIMEOUT] = "invalid_timeout"
                else:
                    return self.async_create_entry(
                        title="HA Monitoring",
                        data={},
                        options={
                            CONF_SCAN_INTERVAL: interval,
                            CONF_OFFLINE_TIMEOUT: timeout,
                        },
                    )
            except ValueError:
                errors["base"] = "invalid_number"

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Renvoie le gestionnaire d'options."""
        return HAMonitoringOptionsFlowHandler(config_entry)


class HAMonitoringOptionsFlowHandler(config_entries.OptionsFlow):
    """Flux de modification des options (bouton CONFIGURER)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Formulaire d'édition des paramètres."""
        errors = {}
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_timeout = self.config_entry.options.get(
            CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT
        )

        if user_input is not None:
            try:
                interval = int(user_input[CONF_SCAN_INTERVAL])
                timeout = int(user_input[CONF_OFFLINE_TIMEOUT])

                if interval < 5:
                    errors[CONF_SCAN_INTERVAL] = "invalid_interval"
                elif timeout < 1:
                    errors[CONF_OFFLINE_TIMEOUT] = "invalid_timeout"
                else:
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_SCAN_INTERVAL: interval,
                            CONF_OFFLINE_TIMEOUT: timeout,
                        },
                    )
            except ValueError:
                errors["base"] = "invalid_number"

        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(current_interval, current_timeout),
            errors=errors,
        )
