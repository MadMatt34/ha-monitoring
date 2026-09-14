"""DataUpdateCoordinator centralisé pour HA Monitoring."""

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import logging
import time
from typing import override

from homeassistant.components.backup import (
    CreateBackupEvent,
    CreateBackupState,
    async_get_manager,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    CoreState,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.translation import (
    async_get_translations,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_STARTUP_DELAY,
    CONF_BATTERY_LOW_THRESHOLD,
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
    DEFAULT_LAST_SEEN_SUFFIX,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
    LOCALIZED_LAST_SEEN_SUFFIX,
    STORAGE_KEY_MAINTENANCE,
    STORAGE_VERSION_MAINTENANCE,
)
from .helpers.backup import async_get_backup_info
from .helpers.system import (
    _snapshot_states,
    async_get_addons,
    async_get_failed_integrations,
    async_get_pending_repairs,
    scan_all_states,
)
from .helpers.system_info import async_get_system_stats
from .helpers.trace import get_trace_errors
from .types import (
    HAMonitoringData,
    MonitoringBackupData,
    SystemStatsData,
    TraceErrorData,
)

_LOGGER = logging.getLogger(__name__)

_HA_START_TIME_KEY = "ha_start_time"
_BACKUP_CACHE_KEY = "backup_cache"
_BACKUP_SCAN_TIME_CACHE_KEY = "backup_scan_timestamp_cache"


class HAMonitoringCoordinator(DataUpdateCoordinator[HAMonitoringData]):
    """Coordinator principal de HA Monitoring."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialise le coordinator."""
        self.entry = entry

        hass.data.setdefault(DOMAIN, {})

        self._ha_start_time: datetime | None = hass.data[DOMAIN].get(_HA_START_TIME_KEY)

        self._is_ready = False
        self._maintenance_mode = False

        self._maintenance_store: Store[dict[str, bool]] = Store(
            hass,
            STORAGE_VERSION_MAINTENANCE,
            STORAGE_KEY_MAINTENANCE,
        )

        # ------------------------------------------------------------------
        # Backup
        # ------------------------------------------------------------------
        self._backup_cache: dict[str, MonitoringBackupData] = hass.data[DOMAIN].setdefault(
            _BACKUP_CACHE_KEY,
            {},
        )

        self._cached_backup_info: MonitoringBackupData | None = self._backup_cache.get(
            entry.entry_id
        )

        self._backup_scan_timestamp_cache: dict[str, datetime] = hass.data[DOMAIN].setdefault(
            _BACKUP_SCAN_TIME_CACHE_KEY,
            {},
        )

        self._last_backup_scan_timestamp: datetime | None = self._backup_scan_timestamp_cache.get(
            entry.entry_id
        )

        self._previous_backup_info: MonitoringBackupData | None = None
        self._last_backup_event: CreateBackupEvent | None = None
        self._last_backup_event_time: datetime | None = None
        self._backup_event_unsub: Callable[[], None] | None = None

        # ------------------------------------------------------------------
        # Démarrage HA
        # ------------------------------------------------------------------
        self._unsub_ha_started: Callable[[], None] | None = None
        self._startup_timer_unsub: Callable[[], None] | None = None

        # ------------------------------------------------------------------
        # Timestamps des derniers scans
        # ------------------------------------------------------------------
        self._last_scan_timestamp: datetime | None = None
        self._last_scan_duration: float | None = None
        self._last_trace_scan_duration: float | None = None
        self._last_system_info_scan_duration: float | None = None
        self._last_backup_scan_duration: float | None = None
        self._scan_timestamp_listeners: list[Callable[[], None]] = []
        self._scan_timestamps_changed = False

        # ------------------------------------------------------------------
        # Cache traces
        # ------------------------------------------------------------------
        self._last_trace_check_time: datetime | None = None
        self._cached_automations: list[TraceErrorData] = []
        self._cached_scripts: list[TraceErrorData] = []

        # ------------------------------------------------------------------
        # Cache System Info
        # ------------------------------------------------------------------
        self._last_system_stats_check_time: datetime | None = None
        self._cached_system_stats: SystemStatsData | None = None

        # ------------------------------------------------------------------
        # Cache traductions utilisées par le scan principal
        # ------------------------------------------------------------------
        self._cached_unknown_platform: str | None = None
        self._cached_unknown_version: str | None = None
        self._cached_translation_language: str | None = None

        scan_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL,
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )

        self._setup_startup_delay()

        try:
            backup_manager = async_get_manager(hass)
        except HomeAssistantError:
            _LOGGER.debug("[HA Monitoring] Le composant Backup n'est pas disponible.")
        else:
            self._backup_event_unsub = backup_manager.async_subscribe_events(
                self._async_backup_event
            )

    async def async_initialize(self) -> None:
        """Initialise les données persistantes du coordinator."""
        stored_data = await self._maintenance_store.async_load()

        if stored_data is None:
            return

        self._maintenance_mode = stored_data.get(
            self.entry.entry_id,
            False,
        )

    @property
    def maintenance_mode(self) -> bool:
        """Retourne l'état du mode maintenance."""
        return self._maintenance_mode

    async def async_set_maintenance_mode(
        self,
        enabled: bool,
    ) -> None:
        """Active ou désactive le mode maintenance."""
        if self._maintenance_mode == enabled:
            return

        self._maintenance_mode = enabled

        stored_data = (await self._maintenance_store.async_load()) or {}

        stored_data[self.entry.entry_id] = enabled

        await self._maintenance_store.async_save(stored_data)

        if enabled:
            await self.async_refresh()
            return

        await self.async_force_refresh()

    async def async_remove_persistent_data(self) -> None:
        """Supprime les données persistantes du mode maintenance."""
        stored_data = (await self._maintenance_store.async_load()) or {}

        if self.entry.entry_id not in stored_data:
            return

        stored_data.pop(self.entry.entry_id)

        await self._maintenance_store.async_save(stored_data)

    def _setup_startup_delay(self) -> None:
        """Configure le délai post-démarrage de Home Assistant."""
        startup_delay = float(
            self.entry.options.get(
                CONF_STARTUP_DELAY,
                DEFAULT_STARTUP_DELAY,
            )
        )

        if self.hass.state == CoreState.running:
            if self._ha_start_time is None:
                self._ha_start_time = dt_util.utcnow()
                self.hass.data[DOMAIN][_HA_START_TIME_KEY] = self._ha_start_time

            elapsed = (dt_util.utcnow() - self._ha_start_time).total_seconds()

            if elapsed >= startup_delay:
                self._is_ready = True
                return

            self._schedule_startup_timer(startup_delay - elapsed)
            return

        self._is_ready = False

        self._unsub_ha_started = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED,
            self._async_home_assistant_started,
        )

    @callback
    def async_add_scan_timestamp_listener(
        self,
        listener: Callable[[], None],
    ) -> Callable[[], None]:
        """Ajoute un listener pour les changements de timestamps."""
        self._scan_timestamp_listeners.append(listener)

        def _remove_listener() -> None:
            if listener in self._scan_timestamp_listeners:
                self._scan_timestamp_listeners.remove(listener)

        return _remove_listener

    @callback
    def _async_update_scan_timestamp_listeners(
        self,
    ) -> None:
        """Notifie les listeners des timestamps."""
        for listener in tuple(self._scan_timestamp_listeners):
            listener()

    @callback
    def _async_home_assistant_started(
        self,
        event: Event,
    ) -> None:
        """Réagit au démarrage officiel de Home Assistant."""
        self._unsub_ha_started = None
        self._ha_start_time = event.time_fired

        self.hass.data[DOMAIN][_HA_START_TIME_KEY] = self._ha_start_time

        startup_delay = float(
            self.entry.options.get(
                CONF_STARTUP_DELAY,
                DEFAULT_STARTUP_DELAY,
            )
        )

        self._schedule_startup_timer(startup_delay)

    @callback
    def _schedule_startup_timer(
        self,
        delay: float,
    ) -> None:
        """Programme la fin du délai de démarrage."""
        if self._startup_timer_unsub is not None:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        if delay <= 0:
            self._finish_startup_delay()
            return

        _LOGGER.info(
            "[HA Monitoring] Home Assistant est démarré. Attente de %.1f s avant le premier scan.",
            delay,
        )

        self._startup_timer_unsub = async_call_later(
            self.hass,
            delay,
            self._async_startup_timer_complete,
        )

    @callback
    def _async_startup_timer_complete(
        self,
        _: datetime,
    ) -> None:
        """Termine le délai de démarrage."""
        self._startup_timer_unsub = None
        self._finish_startup_delay()

    @callback
    def _finish_startup_delay(self) -> None:
        """Marque le coordinator comme prêt."""
        if self._is_ready:
            return

        self._is_ready = True

        _LOGGER.info("[HA Monitoring] Fin du délai de démarrage. Lancement du premier scan.")

        self.entry.async_create_background_task(
            self.hass,
            self.async_refresh(),
            "ha_monitoring_startup_refresh",
        )

    @callback
    def _async_backup_event(
        self,
        event: object,
    ) -> None:
        """Réagit aux événements natifs du Backup Manager."""
        if not isinstance(event, CreateBackupEvent):
            return

        if event.state not in (
            CreateBackupState.COMPLETED,
            CreateBackupState.FAILED,
        ):
            return

        self._previous_backup_info = self._cached_backup_info
        self._last_backup_event = event
        self._last_backup_event_time = dt_util.utcnow()
        self._cached_backup_info = None

        _LOGGER.debug(
            "[HA Monitoring] Événement Backup %s reçu. Actualisation de l'état Backup.",
            event.state.value,
        )

        self.entry.async_create_background_task(
            self.hass,
            self.async_refresh(),
            "ha_monitoring_backup_refresh",
        )

    def _get_last_seen_suffixes(
        self,
    ) -> tuple[str, ...]:
        """Retourne les suffixes last_seen applicables."""
        suffixes = set(DEFAULT_LAST_SEEN_SUFFIX)

        localized_suffix = LOCALIZED_LAST_SEEN_SUFFIX.get(self.hass.config.language)

        if localized_suffix:
            suffixes.add(localized_suffix.lower())

        return tuple(suffixes)

    async def _async_get_common_translations(
        self,
    ) -> tuple[str, str]:
        """Retourne les textes common traduits utilisés par le scan."""
        language = self.hass.config.language

        if (
            self._cached_unknown_platform is not None
            and self._cached_unknown_version is not None
            and self._cached_translation_language == language
        ):
            return (
                self._cached_unknown_platform,
                self._cached_unknown_version,
            )

        translations = await async_get_translations(
            self.hass,
            language,
            "common",
            integrations={DOMAIN},
        )

        self._cached_unknown_platform = translations[f"component.{DOMAIN}.common.unknown"]

        self._cached_unknown_version = translations[f"component.{DOMAIN}.common.unknown_version"]

        self._cached_translation_language = language

        return (
            self._cached_unknown_platform,
            self._cached_unknown_version,
        )

    @property
    def last_scan_timestamp(self) -> datetime | None:
        """Retourne la date du dernier scan principal."""
        return self._last_scan_timestamp

    @property
    def last_scan_duration(self) -> float | None:
        """Retourne la durée du dernier scan principal."""
        return self._last_scan_duration

    @property
    def last_traces_scan_timestamp(
        self,
    ) -> datetime | None:
        """Retourne la date du dernier scan des traces."""
        return self._last_trace_check_time

    @property
    def last_traces_scan_duration(self) -> float | None:
        """Retourne la durée du dernier scan des traces."""
        return self._last_trace_scan_duration

    @property
    def last_system_info_scan_timestamp(
        self,
    ) -> datetime | None:
        """Retourne la date du dernier scan System Info."""
        return self._last_system_stats_check_time

    @property
    def last_system_info_scan_duration(self) -> float | None:
        """Retourne la durée du dernier scan System Info."""
        return self._last_system_info_scan_duration

    @property
    def last_backup_scan_timestamp(
        self,
    ) -> datetime | None:
        """Retourne la date du dernier scan Backup."""
        return self._last_backup_scan_timestamp

    @property
    def last_backup_scan_duration(self) -> float | None:
        """Retourne la durée du dernier scan Backup."""
        return self._last_backup_scan_duration

    async def async_shutdown(self) -> None:
        """Nettoie les listeners et temporisateurs."""
        if self._unsub_ha_started is not None:
            self._unsub_ha_started()
            self._unsub_ha_started = None

        if self._startup_timer_unsub is not None:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        if self._backup_event_unsub is not None:
            self._backup_event_unsub()
            self._backup_event_unsub = None

        self._scan_timestamp_listeners.clear()

        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force un rafraîchissement immédiat."""
        if self._unsub_ha_started is not None:
            self._unsub_ha_started()
            self._unsub_ha_started = None

        if self._startup_timer_unsub is not None:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._is_ready = True

        self._last_trace_check_time = None
        self._last_system_stats_check_time = None
        self._cached_system_stats = None

        await self.async_refresh()

    async def _async_update_data(
        self,
    ) -> HAMonitoringData:
        """Récupère les métriques de HA Monitoring."""
        now = dt_util.utcnow()

        self._scan_timestamps_changed = False

        # ------------------------------------------------------------------
        # BACKUP
        # ------------------------------------------------------------------
        if self._cached_backup_info is None:
            _LOGGER.debug("[HA Monitoring] Interrogation des informations Backup.")

            scan_backup_start = time.monotonic()

            self._cached_backup_info = await async_get_backup_info(
                self.hass,
                backup_event=self._last_backup_event,
                backup_event_time=self._last_backup_event_time,
                previous_info=self._previous_backup_info,
            )

            self._last_backup_scan_duration = time.monotonic() - scan_backup_start
            self.stamp = dt_util.utcnow()

            self._backup_scan_timestamp_cache[self.entry.entry_id] = (
                self._last_backup_scan_timestamp
            )

            self._scan_timestamps_changed = True

            self._backup_cache[self.entry.entry_id] = self._cached_backup_info

            self._previous_backup_info = None
            self._last_backup_event = None
            self._last_backup_event_time = None

        current_backup_info = self._cached_backup_info

        if current_backup_info is None:
            current_backup_info = self._empty_results(in_startup_delay=True)["monitoring_backup"]

        # ------------------------------------------------------------------
        # STARTUP DELAY
        # ------------------------------------------------------------------
        if not self._is_ready:
            results = self._empty_results(in_startup_delay=True)

            results["monitoring_backup"] = current_backup_info

            results["maintenance_mode"] = self._maintenance_mode

            return results

        options = self.entry.options

        offline_timeout = float(
            options.get(
                CONF_OFFLINE_TIMEOUT,
                DEFAULT_OFFLINE_TIMEOUT,
            )
        )

        battery_threshold = float(
            options.get(
                CONF_BATTERY_LOW_THRESHOLD,
                DEFAULT_BATTERY_LOW_THRESHOLD,
            )
        )

        # ------------------------------------------------------------------
        # SYSTEM INFO
        # ------------------------------------------------------------------
        # System Info continue à fonctionner en mode maintenance.
        system_info_scan_interval_hours = float(
            options.get(
                CONF_SYSTEM_INFO_SCAN_INTERVAL,
                DEFAULT_SYSTEM_INFO_SCAN_INTERVAL,
            )
        )

        system_info_scan_interval_sec = system_info_scan_interval_hours * 3600

        if (
            self._last_system_stats_check_time is None
            or self._cached_system_stats is None
            or (now - self._last_system_stats_check_time).total_seconds()
            >= system_info_scan_interval_sec
        ):
            assert self._ha_start_time is not None

            scan_system_start = time.monotonic()

            self._cached_system_stats = await async_get_system_stats(
                self.hass,
                self._ha_start_time,
            )

            self._last_system_info_scan_duration = time.monotonic() - scan_system_start
            self._last_system_stats_check_time = dt_util.utcnow()
            self._scan_timestamps_changed = True

        assert self._cached_system_stats is not None

        # ------------------------------------------------------------------
        # MODE MAINTENANCE
        # ------------------------------------------------------------------
        if self._maintenance_mode:
            return {
                ATTR_STARTUP_DELAY: False,
                "maintenance_mode": True,
                "system_stats": self._cached_system_stats,
                "monitoring_addons": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_integrations": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_automations": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_scripts": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_updates": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_repairs": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_unavailable": {
                    "items": [],
                    "total": 0,
                },
                "monitoring_offline": {
                    "items": [],
                    "total": 0,
                    "timeout": offline_timeout,
                },
                "monitoring_battery": {
                    "items": [],
                    "total": 0,
                    "threshold": battery_threshold,
                },
                "monitoring_backup": current_backup_info,
            }

        excluded_unavailable_entities = options.get(
            CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
            [],
        )

        excluded_unavailable_domains = options.get(
            CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
            DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
        )

        excluded_unavailable_globs = options.get(
            CONF_EXCLUDED_UNAVAILABLE_GLOBS,
            [],
        )

        excluded_batteries = options.get(
            CONF_EXCLUDED_BATTERIES,
            [],
        )

        last_seen_suffixes = self._get_last_seen_suffixes()

        unknown_platform, unknown_version = await self._async_get_common_translations()

        # ------------------------------------------------------------------
        # SCAN PRINCIPAL
        # ------------------------------------------------------------------
        scan_main_start = time.monotonic()

        state_snapshot = _snapshot_states(
            self.hass,
            last_seen_suffixes,
            unknown_platform,
        )

        (
            updates,
            unavailable,
            offline,
            low_batteries,
        ) = await self.hass.async_add_executor_job(
            partial(
                scan_all_states,
                state_snapshot,
                excluded_updates=options.get(
                    CONF_EXCLUDED_UPDATES,
                    [],
                ),
                excluded_unavailable_entities=(excluded_unavailable_entities),
                excluded_unavailable_domains=(excluded_unavailable_domains),
                excluded_offline=options.get(
                    CONF_EXCLUDED_OFFLINE,
                    [],
                ),
                excluded_batteries=excluded_batteries,
                timeout_hours=offline_timeout,
                unknown_version=unknown_version,
                battery_threshold=battery_threshold,
                last_seen_suffixes=(last_seen_suffixes),
                excluded_unavailable_globs=(excluded_unavailable_globs),
            )
        )

        # ------------------------------------------------------------------
        # TRACES
        # ------------------------------------------------------------------
        traces_scan_interval_min = float(
            options.get(
                CONF_TRACES_SCAN_INTERVAL,
                DEFAULT_TRACES_SCAN_INTERVAL,
            )
        )

        traces_scan_interval_sec = traces_scan_interval_min * 60

        if (
            self._last_trace_check_time is None
            or (now - self._last_trace_check_time).total_seconds() >= traces_scan_interval_sec
        ):
            scan_traces_start = time.monotonic()

            self._cached_automations = await get_trace_errors(
                self.hass,
                "automation",
                options.get(
                    CONF_EXCLUDED_AUTOMATIONS,
                    [],
                ),
            )
            self._cached_scripts = await get_trace_errors(
                self.hass,
                "script",
                options.get(
                    CONF_EXCLUDED_SCRIPTS,
                    [],
                ),
            )

            self._last_trace_scan_duration = time.monotonic() - scan_traces_start
            self._last_trace_check_time = dt_util.utcnow()
            self._scan_timestamps_changed = True

        # ------------------------------------------------------------------
        # COLLECTES COURANTES
        # ------------------------------------------------------------------
        addons = await async_get_addons(
            self.hass,
            options.get(
                CONF_EXCLUDED_ADDONS,
                [],
            ),
        )

        integrations = await async_get_failed_integrations(
            self.hass,
            options.get(
                CONF_EXCLUDED_INTEGRATIONS,
                [],
            ),
        )

        repairs = await async_get_pending_repairs(
            self.hass,
            options.get(
                CONF_EXCLUDED_REPAIRS,
                [],
            ),
        )

        self._last_scan_duration = time.monotonic() - scan_main_start
        self._last_scan_timestamp = dt_util.utcnow()
        self._scan_timestamps_changed = True

        return {
            ATTR_STARTUP_DELAY: False,
            "maintenance_mode": False,
            "system_stats": self._cached_system_stats,
            "monitoring_addons": {
                "items": addons,
                "total": len(addons),
            },
            "monitoring_integrations": {
                "items": integrations,
                "total": len(integrations),
            },
            "monitoring_automations": {
                "items": self._cached_automations,
                "total": len(self._cached_automations),
            },
            "monitoring_scripts": {
                "items": self._cached_scripts,
                "total": len(self._cached_scripts),
            },
            "monitoring_updates": {
                "items": updates,
                "total": len(updates),
            },
            "monitoring_repairs": {
                "items": repairs,
                "total": len(repairs),
            },
            "monitoring_unavailable": {
                "items": unavailable,
                "total": len(unavailable),
            },
            "monitoring_offline": {
                "items": offline,
                "total": len(offline),
                "timeout": offline_timeout,
            },
            "monitoring_battery": {
                "items": low_batteries,
                "total": len(low_batteries),
                "threshold": battery_threshold,
            },
            "monitoring_backup": current_backup_info,
        }

    def _empty_results(
        self,
        *,
        in_startup_delay: bool,
    ) -> HAMonitoringData:
        """Génère une structure de données vide cohérente."""
        timeout = float(
            self.entry.options.get(
                CONF_OFFLINE_TIMEOUT,
                DEFAULT_OFFLINE_TIMEOUT,
            )
        )

        battery_threshold = float(
            self.entry.options.get(
                CONF_BATTERY_LOW_THRESHOLD,
                DEFAULT_BATTERY_LOW_THRESHOLD,
            )
        )

        return {
            ATTR_STARTUP_DELAY: in_startup_delay,
            "maintenance_mode": self._maintenance_mode,
            "system_stats": {},
            "monitoring_addons": {
                "items": [],
                "total": 0,
            },
            "monitoring_integrations": {
                "items": [],
                "total": 0,
            },
            "monitoring_automations": {
                "items": [],
                "total": 0,
            },
            "monitoring_scripts": {
                "items": [],
                "total": 0,
            },
            "monitoring_updates": {
                "items": [],
                "total": 0,
            },
            "monitoring_repairs": {
                "items": [],
                "total": 0,
            },
            "monitoring_unavailable": {
                "items": [],
                "total": 0,
            },
            "monitoring_offline": {
                "items": [],
                "total": 0,
                "timeout": timeout,
            },
            "monitoring_battery": {
                "items": [],
                "total": 0,
                "threshold": battery_threshold,
            },
            "monitoring_backup": {
                "is_ok": True,
                "date_last_run": None,
                "date_last_success": None,
                "date_next_schedule": None,
                "size": None,
                "failure": None,
                "failed_agents": [],
                "failed_addons": [],
                "failed_folders": [],
                "current_agent_errors": {},
            },
        }

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Actualise les listeners après un refresh réussi."""
        if self.last_update_success and self._scan_timestamps_changed:
            self._async_update_scan_timestamp_listeners()

        self._scan_timestamps_changed = False


type HAMonitoringConfigEntry = ConfigEntry[HAMonitoringCoordinator]
