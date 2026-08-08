"""Config Flow et Options Flow pour l'intégration HA Monitoring."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector

from .const import (
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_OFFLINE,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
    CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
    CONF_EXCLUDED_UNAVAILABLE_GLOBS,
    CONF_EXCLUDED_UPDATES,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    CONF_SYSTEM_INFO_SCAN_INTERVAL,
    CONF_TRACES_SCAN_INTERVAL,
    DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger("custom_components.ha_monitoring.config_flow")


def _flatten_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Aplatit les données des sections pour les extraire au niveau racine."""
    flat: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def get_schema(
    hass: HomeAssistant | None = None,
    options: dict[str, Any] | None = None,
) -> vol.Schema:
    """Construit le schéma du formulaire avec sélecteurs et exclusions."""
    options = options or {}

    current_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    current_traces_interval = options.get(
        CONF_TRACES_SCAN_INTERVAL, DEFAULT_TRACES_SCAN_INTERVAL
    )
    current_system_info_interval = options.get(
        CONF_SYSTEM_INFO_SCAN_INTERVAL, DEFAULT_SYSTEM_INFO_SCAN_INTERVAL
    )
    current_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)
    current_startup_delay = options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY)

    current_excluded_domains = options.get(
        CONF_EXCLUDED_UNAVAILABLE_DOMAINS, DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS
    )

    domain_options: list[str] = []
    allowed_domains: list[str] | None = None

    if hass is not None:
        entity_ids = hass.states.async_entity_ids()
        all_domains = {entity_id.split(".", 1)[0] for entity_id in entity_ids}

        domain_options = sorted(list(all_domains))
        allowed_domains = sorted(list(all_domains - set(current_excluded_domains)))

    return vol.Schema(
        {
            # --- SECTION 1 : Fréquences & Temporisations ---
            vol.Required("section_timings"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_STARTUP_DELAY,
                            default=current_startup_delay,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1800,
                                step=30,
                                mode="slider",
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_SCAN_INTERVAL,
                            default=current_interval,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=5,
                                max=3600,
                                step=5,
                                mode="slider",
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(
                            CONF_SYSTEM_INFO_SCAN_INTERVAL,
                            default=current_system_info_interval,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=168,
                                step=1,
                                mode="slider",
                                unit_of_measurement="h",
                            )
                        ),
                        vol.Required(
                            CONF_TRACES_SCAN_INTERVAL,
                            default=current_traces_interval,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=1440,
                                step=1,
                                mode="slider",
                                unit_of_measurement="m",
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
                                mode="slider",
                                unit_of_measurement="h",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            # --- SECTION 2 : Exclusions système ---
            vol.Required("section_exclusions_system"): section(
                vol.Schema(
                    {
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
                    }
                ),
                {"collapsed": True},
            ),
            # --- SECTION 3 : Exclusions Mises à jour ---
            vol.Required("section_exclusions_updates"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_UPDATES,
                            default=options.get(CONF_EXCLUDED_UPDATES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="update", multiple=True
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            # --- SECTION 4 : Exclusions Automatisations & Scripts ---
            vol.Required("section_exclusions_scripts"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_AUTOMATIONS,
                            default=options.get(CONF_EXCLUDED_AUTOMATIONS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="automation", multiple=True
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_SCRIPTS,
                            default=options.get(CONF_EXCLUDED_SCRIPTS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="script", multiple=True
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            # --- SECTION 5 : Exclusions Appareils Offline ---
            vol.Required("section_exclusions_offline"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_OFFLINE,
                            default=options.get(CONF_EXCLUDED_OFFLINE) or [],
                        ): selector.DeviceSelector(
                            selector.DeviceSelectorConfig(multiple=True)
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            # --- SECTION 6 : Exclusions Entités Indisponibles ---
            vol.Required("section_exclusions_unavailable"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
                            default=current_excluded_domains,
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=domain_options,
                                custom_value=False,
                                multiple=True,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_UNAVAILABLE_GLOBS,
                            default=options.get(CONF_EXCLUDED_UNAVAILABLE_GLOBS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[], custom_value=True, multiple=True
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
                            default=options.get(CONF_EXCLUDED_UNAVAILABLE_ENTITIES)
                            or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                multiple=True,
                                filter=selector.EntityFilterSelectorConfig(
                                    domain=allowed_domains
                                )
                                if allowed_domains
                                else None,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


class HAMonitoringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux d'installation initiale."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Formulaire initial d'ajout de l'intégration."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            cleaned_input = _flatten_options(user_input)
            return self.async_create_entry(
                title="HA Monitoring",
                data={},
                options=cleaned_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema(self.hass),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Retourne le gestionnaire d'options."""
        return HAMonitoringOptionsFlowHandler()


class HAMonitoringOptionsFlowHandler(config_entries.OptionsFlow):
    """Gère les options avec écrasement plat."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Gère l'étape initiale du menu d'options."""
        if user_input is not None:
            cleaned_options = _flatten_options(user_input)
            return self.async_create_entry(title="", data=cleaned_options)

        return self.async_show_form(
            step_id="init",
            data_schema=get_schema(self.hass, self.config_entry.options),
        )