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
    CONF_STARTUP_DELAY,
    DEFAULT_STARTUP_DELAY,
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


# Dans imports de const.py
# Dans get_schema(options=None):
# À ajouter dans la définition du vol.Schema({...}) :
--------------------
def get_schema(options=None):
    """Construit le schéma du formulaire avec sélecteurs et exclusions."""
    options = options or {}

    current_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    current_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)
    current_startup_delay = options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY)

    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current_interval,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
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
            vol.Required(
                CONF_STARTUP_DELAY,
                default=current_startup_delay,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1800,
                    step=30,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            # Exclusions - Textes / Tags
            vol.Optional(
                CONF_EXCLUDED_ADDONS,
                default=options.get(CONF_EXCLUDED_ADDONS) or [],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            vol.Optional(
                CONF_EXCLUDED_INTEGRATIONS,
                default=options.get(CONF_EXCLUDED_INTEGRATIONS) or [],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            vol.Optional(
                CONF_EXCLUDED_REPAIRS,
                default=options.get(CONF_EXCLUDED_REPAIRS) or [],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[], custom_value=True, multiple=True
                )
            ),
            # Exclusions - Entités Home Assistant
            vol.Optional(
                CONF_EXCLUDED_AUTOMATIONS,
                default=options.get(CONF_EXCLUDED_AUTOMATIONS) or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="automation", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_SCRIPTS,
                default=options.get(CONF_EXCLUDED_SCRIPTS) or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_UPDATES,
                default=options.get(CONF_EXCLUDED_UPDATES) or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="update", multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_UNAVAILABLE,
                default=options.get(CONF_EXCLUDED_UNAVAILABLE) or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=True)
            ),
            vol.Optional(
                CONF_EXCLUDED_OFFLINE,
                default=options.get(CONF_EXCLUDED_OFFLINE) or [],
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
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title="HA Monitoring",
                data={},
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Gestionnaire d'options."""
        return HAMonitoringOptionsFlowHandler()


class HAMonitoringOptionsFlowHandler(config_entries.OptionsFlow):
    """Flux de modification des options (Bouton CONFIGURER)."""

    async def async_step_init(self, user_input=None):
        """Formulaire d'édition des options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(self.config_entry.options),
        )
