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
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UPDATES,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_UNAVAILABLE,
    CONF_EXCLUDED_OFFLINE,
)

_LOGGER = logging.getLogger(__name__)


def get_schema(options=None):
    """Construit le schéma du formulaire avec sélecteurs et exclusions."""
    options = options or {}

    current_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    current_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)

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
            # Exclusions - Textes / Tags
            vol.Optional(
                CONF_EXCLUDED_ADDONS,
                default=options.get(CONF_EXCLUDED_ADDONS, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            vol.Optional(
                CONF_EXCLUDED_INTEGRATIONS,
                default=options.get(CONF_EXCLUDED_INTEGRATIONS, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            vol.Optional(
                CONF_EXCLUDED_REPAIRS,
                default=options.get(CONF_EXCLUDED_REPAIRS, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            # Exclusions - Entités Home Assistant
            vol.Optional(
                CONF_EXCLUDED_AUTOMATIONS,
                default=options.get(CONF_EXCLUDED_AUTOMATIONS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="automation", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_SCRIPTS,
                default=options.get(CONF_EXCLUDED_SCRIPTS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_UPDATES,
                default=options.get(CONF_EXCLUDED_UPDATES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="update", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_UNAVAILABLE,
                default=options.get(CONF_EXCLUDED_UNAVAILABLE, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_OFFLINE,
                default=options.get(CONF_EXCLUDED_OFFLINE, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=True)
            ),
        }
    )


class HAMonitoringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux d'installation initiale."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Formulaire initial d'ajout de l'intégration."""
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
                    options_data = dict(user_input)
                    options_data[CONF_SCAN_INTERVAL] = interval
                    options_data[CONF_OFFLINE_TIMEOUT] = timeout

                    return self.async_create_entry(
                        title="HA Monitoring",
                        data={},
                        options=options_data,
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
        """Gestionnaire d'options."""
        return HAMonitoringOptionsFlowHandler(config_entry)


class HAMonitoringOptionsFlowHandler(config_entries.OptionsFlow):
    """Flux de modification des options (Bouton CONFIGURER)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Formulaire d'édition des options."""
        errors = {}

        if user_input is not None:
            try:
                interval = int(user_input[CONF_SCAN_INTERVAL])
                timeout = int(user_input[CONF_OFFLINE_TIMEOUT])

                if interval < 5:
                    errors[CONF_SCAN_INTERVAL] = "invalid_interval"
                elif timeout < 1:
                    errors[CONF_OFFLINE_TIMEOUT] = "invalid_timeout"
                else:
                    options_data = dict(user_input)
                    options_data[CONF_SCAN_INTERVAL] = interval
                    options_data[CONF_OFFLINE_TIMEOUT] = timeout

                    return self.async_create_entry(
                        title="",
                        data=options_data,
                    )
            except ValueError:
                errors["base"] = "invalid_number"

        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(self.config_entry.options),
            errors=errors,
        )
