"""Support pour la plateforme button de HA Monitoring."""

from collections.abc import Mapping
import logging
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ICON_REFRESH,
    TRANSLATION_KEY_REFRESH,
    UNIQUE_ID_REFRESH,
)
from .coordinator import (
    HAMonitoringConfigEntry,
    HAMonitoringCoordinator,
)
from .entity import HAMonitoringBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HAMonitoringConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure la plateforme button à partir d'une ConfigEntry."""
    coordinator = entry.runtime_data

    async_add_entities([HAMonitoringForceScanButton(coordinator, entry)])


class HAMonitoringForceScanButton(
    HAMonitoringBaseEntity,
    ButtonEntity,
):
    """Bouton permettant de forcer le rafraîchissement."""

    _attr_translation_key = TRANSLATION_KEY_REFRESH
    _attr_icon = ICON_REFRESH

    def __init__(
        self,
        coordinator: HAMonitoringCoordinator,
        entry: HAMonitoringConfigEntry,
    ) -> None:
        """Initialise le bouton."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_{UNIQUE_ID_REFRESH}"
        # Entity ID volontairement statique.
        self.entity_id = f"button.{UNIQUE_ID_REFRESH}"

    @property
    def extra_state_attributes(self) -> Mapping[str, str | None]:
        """Retourne les dates des derniers scans."""
        return {
            "last_scan": self.coordinator.last_scan_time.isoformat()
            if self.coordinator.last_scan_time is not None
            else None,
            "last_traces_scan": (
                self.coordinator.last_traces_scan_time.isoformat()
                if self.coordinator.last_traces_scan_time is not None
                else None
            ),
            "last_system_info_scan": (
                self.coordinator.last_system_info_scan_time.isoformat()
                if self.coordinator.last_system_info_scan_time is not None
                else None
            ),
            "last_backup_scan": (
                self.coordinator.last_backup_scan_time.isoformat()
                if self.coordinator.last_backup_scan_time is not None
                else None
            ),
        }

    @override
    async def async_press(self) -> None:
        """Force un rafraîchissement complet du Coordinator."""
        _LOGGER.info("[HA Monitoring] Bouton appuyé : rafraîchissement forcé en cours.")

        await self.coordinator.async_force_refresh()

    @override
    async def async_added_to_hass(self) -> None:
        """Enregistre le listener dédié aux timestamps de scan."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.coordinator.async_add_scan_timestamp_listener(self._handle_scan_timestamp_update)
        )

    @callback
    def _handle_scan_timestamp_update(self) -> None:
        """Actualise les attributs liés aux timestamps."""
        self.async_write_ha_state()
