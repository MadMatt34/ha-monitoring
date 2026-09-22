"""Config Flow et Options Flow pour l'intégration HA Monitoring."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_EVENT_ADDONS_DECREASE,
    CONF_EVENT_ADDONS_INCREASE,
    CONF_EVENT_AUTOMATIONS_DECREASE,
    CONF_EVENT_AUTOMATIONS_INCREASE,
    CONF_EVENT_BATTERY_DECREASE,
    CONF_EVENT_BATTERY_INCREASE,
    CONF_EVENT_INTEGRATIONS_DECREASE,
    CONF_EVENT_INTEGRATIONS_INCREASE,
    CONF_EVENT_OFFLINE_DECREASE,
    CONF_EVENT_OFFLINE_INCREASE,
    CONF_EVENT_REPAIRS_DECREASE,
    CONF_EVENT_REPAIRS_INCREASE,
    CONF_EVENT_SCRIPTS_DECREASE,
    CONF_EVENT_SCRIPTS_INCREASE,
    CONF_EVENT_UNAVAILABLE_DECREASE,
    CONF_EVENT_UNAVAILABLE_INCREASE,
    CONF_EVENT_UPDATES_DECREASE,
    CONF_EVENT_UPDATES_INCREASE,
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_BATTERIES,
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
    DEFAULT_BATTERY_LOW_THRESHOLD,
    DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger("custom_components.ha_monitoring.config_flow")


def _flatten_options(
    user_input: dict[str, Any],
) -> dict[str, Any]:
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
    """Construit le schéma du formulaire initial."""
    options = options or {}
    current_interval = options.get(
        CONF_SCAN_INTERVAL,
        DEFAULT_SCAN_INTERVAL,
    )
    current_traces_interval = options.get(
        CONF_TRACES_SCAN_INTERVAL,
        DEFAULT_TRACES_SCAN_INTERVAL,
    )
    current_system_info_interval = options.get(
        CONF_SYSTEM_INFO_SCAN_INTERVAL,
        DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
    )
    current_timeout = options.get(
        CONF_OFFLINE_TIMEOUT,
        DEFAULT_OFFLINE_TIMEOUT,
    )
    current_startup_delay = options.get(
        CONF_STARTUP_DELAY,
        DEFAULT_STARTUP_DELAY,
    )
    current_excluded_domains = options.get(
        CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
        DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    )
    current_battery_threshold = options.get(
        CONF_BATTERY_LOW_THRESHOLD,
        DEFAULT_BATTERY_LOW_THRESHOLD,
    )
    current_excluded_batteries = options.get(
        CONF_EXCLUDED_BATTERIES,
        [],
    )
    domain_options: list[str] = []
    allowed_domains: list[str] | None = None

    if hass is not None:
        entity_ids = hass.states.async_entity_ids()
        all_domains = {entity_id.split(".", 1)[0] for entity_id in entity_ids}

        domain_options = sorted(all_domains)
        allowed_domains = sorted(all_domains - set(current_excluded_domains))

    return vol.Schema(
        {
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
                        vol.Required(
                            CONF_BATTERY_LOW_THRESHOLD,
                            default=current_battery_threshold,
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=100,
                                step=1,
                                mode="slider",
                                unit_of_measurement="%",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_system"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_ADDONS,
                            default=options.get(CONF_EXCLUDED_ADDONS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_INTEGRATIONS,
                            default=options.get(CONF_EXCLUDED_INTEGRATIONS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_REPAIRS,
                            default=options.get(CONF_EXCLUDED_REPAIRS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_updates"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_UPDATES,
                            default=options.get(CONF_EXCLUDED_UPDATES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="update",
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_scripts"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_AUTOMATIONS,
                            default=options.get(CONF_EXCLUDED_AUTOMATIONS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="automation",
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_SCRIPTS,
                            default=options.get(CONF_EXCLUDED_SCRIPTS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="script",
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_offline"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_OFFLINE,
                            default=options.get(CONF_EXCLUDED_OFFLINE) or [],
                        ): selector.DeviceSelector(selector.DeviceSelectorConfig(multiple=True)),
                    }
                ),
                {"collapsed": True},
            ),
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
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
                            default=options.get(CONF_EXCLUDED_UNAVAILABLE_ENTITIES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                multiple=True,
                                filter=(
                                    selector.EntityFilterSelectorConfig(domain=allowed_domains)
                                    if allowed_domains
                                    else None
                                ),
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_battery"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_BATTERIES,
                            default=current_excluded_batteries,
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                multiple=True,
                                filter=selector.EntityFilterSelectorConfig(
                                    domain="sensor",
                                    device_class="battery",
                                ),
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def get_timings_schema(
    options: dict[str, Any],
) -> vol.Schema:
    """Construit la page des délais, fréquences et seuils."""
    return vol.Schema(
        {
            vol.Required("section_delays"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_STARTUP_DELAY,
                            default=options.get(
                                CONF_STARTUP_DELAY,
                                DEFAULT_STARTUP_DELAY,
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1800,
                                step=30,
                                mode="slider",
                                unit_of_measurement="s",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_timings"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_SCAN_INTERVAL,
                            default=options.get(
                                CONF_SCAN_INTERVAL,
                                DEFAULT_SCAN_INTERVAL,
                            ),
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
                            default=options.get(
                                CONF_SYSTEM_INFO_SCAN_INTERVAL,
                                DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
                            ),
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
                            default=options.get(
                                CONF_TRACES_SCAN_INTERVAL,
                                DEFAULT_TRACES_SCAN_INTERVAL,
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=1440,
                                step=1,
                                mode="slider",
                                unit_of_measurement="m",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_thresholds"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_OFFLINE_TIMEOUT,
                            default=options.get(
                                CONF_OFFLINE_TIMEOUT,
                                DEFAULT_OFFLINE_TIMEOUT,
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=720,
                                step=1,
                                mode="slider",
                                unit_of_measurement="h",
                            )
                        ),
                        vol.Required(
                            CONF_BATTERY_LOW_THRESHOLD,
                            default=options.get(
                                CONF_BATTERY_LOW_THRESHOLD,
                                DEFAULT_BATTERY_LOW_THRESHOLD,
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=100,
                                step=1,
                                mode="slider",
                                unit_of_measurement="%",
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def get_exclusions_schema(
    hass: HomeAssistant,
    options: dict[str, Any],
) -> vol.Schema:
    """Construit la page des exclusions."""
    current_excluded_domains = options.get(
        CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
        DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    )

    entity_ids = hass.states.async_entity_ids()
    all_domains = {entity_id.split(".", 1)[0] for entity_id in entity_ids}
    domain_options = sorted(all_domains)
    allowed_domains = sorted(all_domains - set(current_excluded_domains))

    return vol.Schema(
        {
            vol.Required("section_exclusions_system"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_ADDONS,
                            default=options.get(CONF_EXCLUDED_ADDONS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_INTEGRATIONS,
                            default=options.get(CONF_EXCLUDED_INTEGRATIONS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_REPAIRS,
                            default=options.get(CONF_EXCLUDED_REPAIRS) or [],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_updates"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_UPDATES,
                            default=options.get(CONF_EXCLUDED_UPDATES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="update",
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_scripts"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_AUTOMATIONS,
                            default=options.get(CONF_EXCLUDED_AUTOMATIONS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="automation",
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_SCRIPTS,
                            default=options.get(CONF_EXCLUDED_SCRIPTS) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="script",
                                multiple=True,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_offline"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_OFFLINE,
                            default=options.get(CONF_EXCLUDED_OFFLINE) or [],
                        ): selector.DeviceSelector(selector.DeviceSelectorConfig(multiple=True)),
                    }
                ),
                {"collapsed": True},
            ),
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
                                options=[],
                                custom_value=True,
                                multiple=True,
                            )
                        ),
                        vol.Optional(
                            CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
                            default=options.get(CONF_EXCLUDED_UNAVAILABLE_ENTITIES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                multiple=True,
                                filter=(
                                    selector.EntityFilterSelectorConfig(domain=allowed_domains)
                                    if allowed_domains
                                    else None
                                ),
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_exclusions_battery"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_EXCLUDED_BATTERIES,
                            default=options.get(CONF_EXCLUDED_BATTERIES) or [],
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                multiple=True,
                                filter=selector.EntityFilterSelectorConfig(
                                    domain="sensor",
                                    device_class="battery",
                                ),
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def get_events_schema(
    options: dict[str, Any],
) -> vol.Schema:
    """Construit la page des événements de surveillance."""
    return vol.Schema(
        {
            vol.Required("section_events_increase"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_EVENT_ADDONS_INCREASE,
                            default=options.get(
                                CONF_EVENT_ADDONS_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_INTEGRATIONS_INCREASE,
                            default=options.get(
                                CONF_EVENT_INTEGRATIONS_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_AUTOMATIONS_INCREASE,
                            default=options.get(
                                CONF_EVENT_AUTOMATIONS_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_SCRIPTS_INCREASE,
                            default=options.get(
                                CONF_EVENT_SCRIPTS_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_UPDATES_INCREASE,
                            default=options.get(
                                CONF_EVENT_UPDATES_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_REPAIRS_INCREASE,
                            default=options.get(
                                CONF_EVENT_REPAIRS_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_UNAVAILABLE_INCREASE,
                            default=options.get(
                                CONF_EVENT_UNAVAILABLE_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_OFFLINE_INCREASE,
                            default=options.get(
                                CONF_EVENT_OFFLINE_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_BATTERY_INCREASE,
                            default=options.get(
                                CONF_EVENT_BATTERY_INCREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("section_events_decrease"): section(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_EVENT_ADDONS_DECREASE,
                            default=options.get(
                                CONF_EVENT_ADDONS_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_INTEGRATIONS_DECREASE,
                            default=options.get(
                                CONF_EVENT_INTEGRATIONS_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_AUTOMATIONS_DECREASE,
                            default=options.get(
                                CONF_EVENT_AUTOMATIONS_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_SCRIPTS_DECREASE,
                            default=options.get(
                                CONF_EVENT_SCRIPTS_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_UPDATES_DECREASE,
                            default=options.get(
                                CONF_EVENT_UPDATES_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_REPAIRS_DECREASE,
                            default=options.get(
                                CONF_EVENT_REPAIRS_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_UNAVAILABLE_DECREASE,
                            default=options.get(
                                CONF_EVENT_UNAVAILABLE_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_OFFLINE_DECREASE,
                            default=options.get(
                                CONF_EVENT_OFFLINE_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                        vol.Required(
                            CONF_EVENT_BATTERY_DECREASE,
                            default=options.get(
                                CONF_EVENT_BATTERY_DECREASE,
                                False,
                            ),
                        ): selector.BooleanSelector(),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


class HAMonitoringConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Flux d'installation initiale."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
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
    """Gère les options avec un menu en trois pages."""

    def __init__(self) -> None:
        """Initialise le gestionnaire d'options."""
        self._options: dict[str, Any] | None = None

    def _get_options(self) -> dict[str, Any]:
        """Retourne une copie mutable des options actuelles."""
        if self._options is None:
            self._options = dict(self.config_entry.options)

        return self._options

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Affiche le menu principal des options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "timings",
                "exclusions",
                "events",
                "done",
            ],
        )

    async def async_step_timings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure les délais, fréquences et seuils."""
        options = self._get_options()

        if user_input is not None:
            options.update(_flatten_options(user_input))
            return await self.async_step_init()

        return self.async_show_form(
            step_id="timings",
            data_schema=get_timings_schema(options),
        )

    async def async_step_exclusions(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure les exclusions."""
        options = self._get_options()

        if user_input is not None:
            options.update(_flatten_options(user_input))
            return await self.async_step_init()

        return self.async_show_form(
            step_id="exclusions",
            data_schema=get_exclusions_schema(
                self.hass,
                options,
            ),
        )

    async def async_step_events(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure les événements de surveillance."""
        options = self._get_options()

        if user_input is not None:
            options.update(_flatten_options(user_input))
            return await self.async_step_init()

        return self.async_show_form(
            step_id="events",
            data_schema=get_events_schema(options),
        )

    async def async_step_done(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Enregistre les options et termine le flow."""
        return self.async_create_entry(
            title="",
            data=self._get_options(),
        )
