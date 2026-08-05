"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""
import logging
from datetime import datetime, timedelta, time

from homeassistant.const import (STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.loader import async_get_integration
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_OFFLINE,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UPDATES,
    CONF_EXCLUDED_UNAVAILABLE_ENTITIES,
    CONF_EXCLUDED_UNAVAILABLE_DOMAINS,
    DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS,
    CONF_OFFLINE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_STARTUP_DELAY,
    CONF_TRACES_SCAN_INTERVAL,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_TRACES_SCAN_INTERVAL,
    DOMAIN,
    INTEGRATION_ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_LAST_SEEN_ATTRS = ("last_seen", "last_reported", "last_seen_timestamp")


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


def _format_date_local(val) -> str | None:
    """Convertit un datetime ou un timestamp au format ISO local."""
    if val is None or val == "":
        return None

    dt_obj = None
    if isinstance(val, datetime):
        dt_obj = val
    elif isinstance(val, (int, float)):
        try:
            dt_obj = dt_util.utc_from_timestamp(val)
        except Exception:
            pass
    elif isinstance(val, str):
        dt_obj = dt_util.parse_datetime(val)
        if not dt_obj:
            return val

    if dt_obj:
        if dt_obj.tzinfo is None:
            dt_obj = dt_util.as_utc(dt_obj)
        return dt_util.as_local(dt_obj).isoformat()

    return str(val)


class HAMonitoringCoordinator(DataUpdateCoordinator):
    """Coordinator principal gérant les collectes et la temporisation."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        if "ha_start_time" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["ha_start_time"] = dt_util.utcnow()

        self._ha_start_time = hass.data[DOMAIN]["ha_start_time"]
        self._skip_startup_delay = False
        self._cached_backup_info = None
        self._last_backup_failure_reason = None
        self._startup_timer_unsub = None
        self._bus_listeners_unsub = []

        self._last_trace_check_time = None
        self._cached_automations = []
        self._cached_scripts = []

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

        self._setup_backup_listeners()

    async def _async_get_last_seen_suffixes(self) -> tuple[str, ...]:
        """Charge le suffixe localisé depuis les fichiers de traduction HA."""
        suffixes = set(DEFAULT_LAST_SEEN_ATTRS)
        try:
            translations = await async_get_translations(
                self.hass,
                self.hass.config.language,
                "config",
                integrations=[DOMAIN],
            )
            key = f"component.{DOMAIN}.config.last_seen_suffix"
            if key in translations and translations[key]:
                suffixes.add(translations[key].lower())
        except Exception as err:
            _LOGGER.debug("Erreur lors du chargement de la traduction last_seen_suffix : %s", err)

        return tuple(suffixes)

    def _setup_backup_listeners(self) -> None:
        """Écoute les événements déclenchés à la fin d'une sauvegarde."""
        async def _async_on_backup_event(event):
            _LOGGER.debug(
                "Fin de sauvegarde détectée via l'événement '%s'.",
                event.event_type,
            )
            if event.event_type == "backup_failed" or event.data.get("status") == "failed":
                self._last_backup_failure_reason = (
                    event.data.get("reason")
                    or event.data.get("error")
                    or event.data.get("message")
                    or "Échec de sauvegarde signalé par événement"
                )

            self._cached_backup_info = await self._async_get_backup_info()
            self.async_update_listeners()

        for event_type in (
            "backup_completed",
            "backup_successful",
            "backup_failed",
            "hassio_backup_completed",
        ):
            unsub = self.hass.bus.async_listen(event_type, _async_on_backup_event)
            self._bus_listeners_unsub.append(unsub)

    async def async_shutdown(self) -> None:
        """Libère les ressources et détruit les écouteurs."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        for unsub in self._bus_listeners_unsub:
            unsub()
        self._bus_listeners_unsub.clear()

        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force le rafraîchissement immédiat de toutes les données."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._skip_startup_delay = True
        self._last_trace_check_time = None
        self._cached_backup_info = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Récupère les métriques système."""
        startup_delay = float(self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._ha_start_time).total_seconds()

        in_startup_phase = (
            not self._skip_startup_delay
            and (self.hass.state != CoreState.running or elapsed_seconds < (startup_delay - 0.5))
        )

        if self._cached_backup_info is None:
            self._cached_backup_info = await self._async_get_backup_info()

        if in_startup_phase:
            remaining = max(0.0, startup_delay - elapsed_seconds)

            if not self._startup_timer_unsub and remaining > 0:
                @callback
                def _force_refresh_after_delay(_):
                    self._startup_timer_unsub = None
                    self.hass.async_create_task(self.async_refresh())

                self._startup_timer_unsub = async_call_later(
                    self.hass, remaining + 0.1, _force_refresh_after_delay
                )

            results = self._empty_results(in_startup_delay=True)
            results["monitoring_backup"] = self._cached_backup_info
            return results

        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        options = self.entry.options
        offline_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)

        excluded_unavailable_entities = options.get(CONF_EXCLUDED_UNAVAILABLE_ENTITIES, [])
        excluded_unavailable_domains = options.get(
            CONF_EXCLUDED_UNAVAILABLE_DOMAINS, DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS
        )

        # Récupération dynamique des termes de connexion localisés
        last_seen_suffixes = await self._async_get_last_seen_suffixes()

        updates, unavailable, offline = self._scan_all_states(
            excluded_updates=options.get(CONF_EXCLUDED_UPDATES, []),
            excluded_unavailable_entities=excluded_unavailable_entities,
            excluded_unavailable_domains=excluded_unavailable_domains,
            excluded_offline=options.get(CONF_EXCLUDED_OFFLINE, []),
            timeout_hours=offline_timeout,
            last_seen_suffixes=last_seen_suffixes,
        )

        traces_scan_interval_min = options.get(
            CONF_TRACES_SCAN_INTERVAL, DEFAULT_TRACES_SCAN_INTERVAL
        )
        traces_scan_interval_sec = float(traces_scan_interval_min) * 60

        if (
            self._last_trace_check_time is None
            or (now - self._last_trace_check_time).total_seconds() >= traces_scan_interval_sec
        ):
            self._cached_automations = self._get_trace_errors(
                "automation", options.get(CONF_EXCLUDED_AUTOMATIONS, [])
            )
            self._cached_scripts = self._get_trace_errors(
                "script", options.get(CONF_EXCLUDED_SCRIPTS, [])
            )
            self._last_trace_check_time = now

        addons = await self._async_get_addons(options.get(CONF_EXCLUDED_ADDONS, []))
        integrations = await self._async_get_failed_integrations(options.get(CONF_EXCLUDED_INTEGRATIONS, []))
        repairs = await self._async_get_pending_repairs(options.get(CONF_EXCLUDED_REPAIRS, []))

        return {
            "in_startup_delay": False,
            "monitoring_addons": {"items": addons, "total": len(addons)},
            "monitoring_integrations": {"items": integrations, "total": len(integrations)},
            "monitoring_automations": {
                "items": self._cached_automations,
                "total": len(self._cached_automations),
            },
            "monitoring_scripts": {
                "items": self._cached_scripts,
                "total": len(self._cached_scripts),
            },
            "monitoring_updates": {"items": updates, "total": len(updates)},
            "monitoring_repairs": {"items": repairs, "total": len(repairs)},
            "monitoring_unavailable": {"items": unavailable, "total": len(unavailable)},
            "monitoring_offline": {
                "items": offline,
                "total": len(offline),
                "timeout": offline_timeout,
            },
            "monitoring_backup": self._cached_backup_info,
        }

    def _scan_all_states(
        self,
        excluded_updates: list,
        excluded_unavailable_entities: list,
        excluded_unavailable_domains: list,
        excluded_offline: list,
        timeout_hours: float,
        last_seen_suffixes: tuple[str, ...] = DEFAULT_LAST_SEEN_ATTRS,
    ) -> tuple[list, list, list]:
        """Parcourt TOUS les états HA en une seule passe."""
        now = dt_util.utcnow()
        cutoff = now - timedelta(hours=float(timeout_hours))

        updates = []
        unavailable = []
        offline = []

        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        for state_obj in self.hass.states.async_all():
            entity_id = state_obj.entity_id
            domain = state_obj.domain
            friendly_name = state_obj.attributes.get("friendly_name") or entity_id

            # Ignorer automatiquement les entités de l'intégration HA Monitoring
            entity_entry = ent_reg.async_get(entity_id)
            if entity_entry and entity_entry.platform == DOMAIN:
                continue

            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                if entity_id not in excluded_unavailable_entities and domain not in excluded_unavailable_domains:
                    unavailable.append(
                        {
                            "entity_id": entity_id,
                            "name": friendly_name,
                            "domain": domain,
                            "state": state_obj.state,
                        }
                    )
                continue

            if state_obj.domain == "update" and state_obj.state == "on":
                if entity_id not in excluded_updates:
                    installed_version = state_obj.attributes.get("installed_version") or "Inconnue"
                    latest_version = state_obj.attributes.get("latest_version") or "Inconnue"

                    updates.append(
                        {
                            "entity_id": entity_id,
                            "name": friendly_name,
                            "installed_version": installed_version,
                            "latest_version": latest_version,
                        }
                    )
                continue

            # --- DÉTECTION HORS-LIGNE (LAST_SEEN) ---
            if entity_id.endswith(last_seen_suffixes):
                if state_obj.state == STATE_UNAVAILABLE:
                    continue

                entity_entry = ent_reg.async_get(entity_id)
                device_id = entity_entry.device_id if entity_entry else None

                # Exclusions : On ignore l'entité si son Appareil (device_id) 
                # ou son Entity ID / Nom figure dans la liste d'exclusions.
                if (device_id and device_id in excluded_offline) or entity_id in excluded_offline:
                    continue

                device_name = None
                platform = "inconnu"

                if entity_entry:
                    platform = entity_entry.platform or "inconnu"
                    if device_id:
                        device_entry = dev_reg.async_get(device_id)
                        if device_entry:
                            device_name = device_entry.name_by_user or device_entry.name

                display_name = device_name or friendly_name

                # Vérification complémentaire sur le nom d'affichage de l'appareil
                if display_name in excluded_offline:
                    continue

                # Récupération et parsing du timestamp last_seen
                last_seen_dt = dt_util.parse_datetime(str(state_obj.state))

                if not last_seen_dt and state_obj.attributes:
                    attrs = state_obj.attributes
                    for attr_key in last_seen_suffixes:
                        val = attrs.get(attr_key)
                        if val is not None:
                            if isinstance(val, (int, float)):
                                try:
                                    ts = val / 1000.0 if val > 1e11 else float(val)
                                    last_seen_dt = dt_util.utc_from_timestamp(ts)
                                except Exception:
                                    pass
                            elif isinstance(val, str):
                                last_seen_dt = dt_util.parse_datetime(val)
                            elif isinstance(val, datetime):
                                last_seen_dt = val

                            if last_seen_dt:
                                break

                if last_seen_dt:
                    last_seen_dt = dt_util.as_utc(last_seen_dt)

                # Si le délai dépasse le timeout configuré
                if last_seen_dt and last_seen_dt < cutoff:
                    if not any(item["device"] == display_name for item in offline):
                        offline.append(
                            {
                                "device": display_name,
                                "date": _format_date_local(last_seen_dt),
                                "platform": platform,
                            }
                        )

        return updates, unavailable, offline

    def _empty_results(self, in_startup_delay: bool) -> dict:
        timeout = self.entry.options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)
        return {
            "in_startup_delay": in_startup_delay,
            "monitoring_addons": {"items": [], "total": 0},
            "monitoring_integrations": {"items": [], "total": 0},
            "monitoring_automations": {"items": [], "total": 0},
            "monitoring_scripts": {"items": [], "total": 0},
            "monitoring_updates": {"items": [], "total": 0},
            "monitoring_repairs": {"items": [], "total": 0},
            "monitoring_unavailable": {"items": [], "total": 0},
            "monitoring_offline": {"items": [], "total": 0, "timeout": timeout},
            "monitoring_backup": {
                "is_ok": True,
                "date_last_run": None,
                "date_last_success": None,
                "date_next_schedule": "Démarrage...",
                "size": None,
                "failure": None,
            },
        }

    def _format_size(self, size_val) -> str | None:
        if size_val is None:
            return None

        if isinstance(size_val, (int, float)):
            if size_val > 10240:
                mb = size_val / (1024 * 1024)
            else:
                mb = float(size_val)

            if mb >= 1024:
                return f"{round(mb / 1024, 2)} Go"
            return f"{round(mb, 2)} Mo"
        return str(size_val)

    def _calculate_next_backup(self, schedule_state, schedule_time_obj) -> datetime | None:
        """Calcule la date de la prochaine sauvegarde."""
        try:
            state_str = str(schedule_state).split('.')[-1].lower()
            if not state_str or state_str == "never":
                return None

            now = dt_util.now()

            if isinstance(schedule_time_obj, time):
                h, m = schedule_time_obj.hour, schedule_time_obj.minute
            elif hasattr(schedule_time_obj, "hour") and hasattr(schedule_time_obj, "minute"):
                h, m = schedule_time_obj.hour, schedule_time_obj.minute
            else:
                parts = str(schedule_time_obj).split(":")
                h, m = int(parts[0]), int(parts[1])

            target_time = time(hour=h, minute=m)
            target_dt = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)

            if state_str == "daily":
                if now >= target_dt:
                    target_dt += timedelta(days=1)
                return target_dt

            days = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            if state_str in days:
                target_day = days[state_str]
                current_day = now.weekday()

                days_ahead = target_day - current_day
                if days_ahead < 0 or (days_ahead == 0 and now >= target_dt):
                    days_ahead += 7

                target_dt += timedelta(days=days_ahead)
                return target_dt

        except Exception as err:
            _LOGGER.debug("Erreur calcul prochaine sauvegarde : %s", err)

        return None

    async def _async_get_backup_info(self) -> dict:
        """Interroge le gestionnaire officiel (Backup Core / Supervisor)."""
        backups_list = []
        next_scheduled = None

        if is_hassio_running(self.hass):
            try:
                client = self.hass.data.get("hassio")
                if client:
                    backups_info = None
                    if hasattr(client, "async_get_backups"):
                        backups_info = await client.async_get_backups()
                    elif hasattr(client, "send_command"):
                        backups_info = await client.send_command("/backups", method="get")

                    if isinstance(backups_info, dict):
                        if "data" in backups_info and isinstance(backups_info["data"], dict):
                            backups_list = backups_info["data"].get("backups", [])
                        elif "backups" in backups_info:
                            backups_list = backups_info.get("backups", [])
            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Hassio : %s", err)

        if "backup" in self.hass.data:
            try:
                backup_manager = self.hass.data["backup"]
                raw_backups = None

                if not backups_list:
                    if hasattr(backup_manager, "async_get_backups"):
                        raw_backups = await backup_manager.async_get_backups()
                    elif hasattr(backup_manager, "backups"):
                        raw_backups = backup_manager.backups

                    if isinstance(raw_backups, dict):
                        for b in raw_backups.values():
                            if isinstance(b, dict):
                                backups_list.append(b)
                            else:
                                backups_list.append({
                                    "slug": getattr(b, "slug", None) or getattr(b, "id", ""),
                                    "name": getattr(b, "name", ""),
                                    "date": getattr(b, "date", None),
                                    "size": getattr(b, "size", 0),
                                    "failed": getattr(b, "failed", False) or getattr(b, "status", "") == "failed",
                                    "reason": getattr(b, "reason", None) or getattr(b, "error", None),
                                })

                if hasattr(backup_manager, "async_get_config") or hasattr(backup_manager, "config"):
                    try:
                        cfg = None
                        if hasattr(backup_manager, "async_get_config"):
                            cfg = await backup_manager.async_get_config()
                        else:
                            cfg = backup_manager.config

                        state = None
                        time_val = None

                        if isinstance(cfg, dict):
                            cb = cfg.get("create_backup", {})
                            if isinstance(cb, dict):
                                state = cb.get("state")
                                time_val = cb.get("time")
                        else:
                            cb = getattr(cfg, "create_backup", None)
                            if cb:
                                state = getattr(cb, "state", None)
                                time_val = getattr(cb, "time", None)
                                if hasattr(state, "value"):
                                    state = state.value

                        if state and time_val:
                            next_scheduled = self._calculate_next_backup(state, time_val)
                    except Exception as err:
                        _LOGGER.debug("Erreur async_get_config backup : %s", err)

            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Backup Core : %s", err)

        if not next_scheduled:
            ent_reg = er.async_get(self.hass)
            for entity_id, entity_entry in ent_reg.entities.items():
                if entity_entry.platform == "backup" and entity_entry.domain == "sensor":
                    state_obj = self.hass.states.get(entity_id)
                    if state_obj and state_obj.state not in (STATE_UNAVAILABLE, None, ""):
                        parsed_dt = dt_util.parse_datetime(state_obj.state)
                        if parsed_dt and parsed_dt > dt_util.utcnow():
                            next_scheduled = parsed_dt
                            break

        if not backups_list:
            return {
                "is_ok": False,
                "date_last_run": None,
                "date_last_success": None,
                "date_next_schedule": _format_date_local(next_scheduled) if next_scheduled else "Not planned",
                "size": None,
                "failure": self._last_backup_failure_reason or "No backup available",
            }

        def get_date(b):
            d = b.get("date")
            if isinstance(d, datetime):
                return dt_util.as_utc(d)
            if isinstance(d, str):
                parsed = dt_util.parse_datetime(d)
                if parsed:
                    return dt_util.as_utc(parsed)
            return datetime.min.replace(tzinfo=dt_util.UTC)

        sorted_backups = sorted(backups_list, key=get_date, reverse=True)
        latest_backup = sorted_backups[0]

        is_failed = latest_backup.get("failed", False) or latest_backup.get("status") == "failed"
        is_ok = not is_failed

        failure = self._last_backup_failure_reason
        if is_failed:
            failure = (
                latest_backup.get("reason")
                or latest_backup.get("error")
                or latest_backup.get("failure_reason")
                or self._last_backup_failure_reason
                or "Unknown failure reason"
            )
            self._last_backup_failure_reason = failure

        last_dt = get_date(latest_backup)
        date_last_run = _format_date_local(last_dt) if last_dt != datetime.min.replace(tzinfo=dt_util.UTC) else _format_date_local(latest_backup.get("date"))

        last_successful_dt = None
        for b in sorted_backups:
            if not b.get("failed", False) and b.get("status") != "failed":
                last_successful_dt = get_date(b)
                break

        if last_successful_dt and last_successful_dt != datetime.min.replace(tzinfo=dt_util.UTC):
            date_last_success = _format_date_local(last_successful_dt)
        else:
            date_last_success = date_last_run if is_ok else "Aucune"

        date_next_schedule = _format_date_local(next_scheduled) if next_scheduled else "Non planifiée"
        size = self._format_size(latest_backup.get("size"))

        return {
            "is_ok": is_ok,
            "date_last_run": date_last_run,
            "date_last_success": date_last_success,
            "date_next_schedule": date_next_schedule,
            "size": size,
            "failure": failure,
        }

    async def _async_get_addons(self, excluded: list) -> list:
        if not is_hassio_running(self.hass):
            return []
        client = self.hass.data.get("hassio")
        if not client:
            return []

        try:
            if hasattr(client, "async_get_addons_info"):
                addons_info = await client.async_get_addons_info()
            elif hasattr(client, "get_addons_info"):
                addons_info = await client.get_addons_info()
            else:
                return []

            addons = addons_info.get("addons", [])
            failed = []
            for addon in addons:
                name = addon.get("name", "")
                slug = addon.get("slug", "")
                if name in excluded or slug in excluded:
                    continue

                if (addon.get("watchdog", False) or addon.get("boot") == "auto") and addon.get(
                    "state"
                ) in ["stopped", "unknown"]:
                    failed.append(name or slug)
            return failed
        except Exception as err:
            _LOGGER.error("Erreur HA Monitoring Addons : %s", err)
            return []

    async def _async_get_failed_integrations(self, excluded: list) -> list:
        """Récupère les intégrations en erreur avec la raison traduite."""
        error_states = {
            ConfigEntryState.SETUP_ERROR,
            ConfigEntryState.SETUP_RETRY,
            ConfigEntryState.MIGRATION_ERROR,
        }

        entries = [
            entry
            for entry in self.hass.config_entries.async_entries()
            if entry.state in error_states
            and entry.domain not in excluded
            and entry.title not in excluded
            and entry.entry_id not in excluded
        ]

        if not entries:
            return []

        domains = {entry.domain for entry in entries}

        # 1. Chargement des noms officiels des intégrations (catégorie "title")
        integration_titles = {}
        try:
            integration_titles = await async_get_translations(
                self.hass,
                self.hass.config.language,
                "title",
                domains=domains,
            )
        except Exception:
            integration_titles = {}

        # 2. Chargement des traductions (HA inclut automatiquement custom_components/ha_monitoring/translations/)
        domains_for_issues = domains | {DOMAIN}
        translations = {}
        try:
            translations = await async_get_translations(
                self.hass,
                self.hass.config.language,
                "issues",
                domains=domains_for_issues,
            )
        except Exception:
            translations = {}

        failed_entries = []

        for entry in entries:
            # Récupération du nom officiel de l'intégration (ex: "Philips Hue" et non "Hue Salon")
            title_key = f"component.{entry.domain}.title"
            integration_name = (
                integration_titles.get(title_key)
                or entry.domain.replace("_", " ").title()
            )

            # Récupération et traduction de la raison d'erreur
            raw_reason = getattr(entry, "reason", None)
            friendly_reason = None

            if raw_reason:
                error_key = f"component.{entry.domain}.config.error.{raw_reason}"
                abort_key = f"component.{entry.domain}.config.abort.{raw_reason}"

                if error_key in translations:
                    friendly_reason = translations[error_key]
                elif abort_key in translations:
                    friendly_reason = translations[abort_key]
                else:
                    friendly_reason = raw_reason

            # Fallbacks depuis fr.json / en.json de ha_monitoring
            if not friendly_reason:
                if entry.state == ConfigEntryState.SETUP_RETRY:
                    friendly_reason = translations.get(
                        f"component.{DOMAIN}.issues.setup_retry.title",
                        "Connexion temporairement impossible",
                    )
                elif entry.state == ConfigEntryState.SETUP_ERROR:
                    friendly_reason = translations.get(
                        f"component.{DOMAIN}.issues.setup_error.title",
                        "Échec d'initialisation ou erreur de configuration",
                    )
                elif entry.state == ConfigEntryState.MIGRATION_ERROR:
                    friendly_reason = translations.get(
                        f"component.{DOMAIN}.issues.migration_error.title",
                        "Erreur lors de la migration des données",
                    )
                else:
                    raw_unknown = translations.get(
                        f"component.{DOMAIN}.issues.unknown_error.title",
                        "État anormal ({state})",
                    )
                    friendly_reason = raw_unknown.format(state=entry.state.value)

            failed_entries.append({
                "name": integration_name,
                "domain": entry.domain,
                "entry_id": entry.entry_id,
                "state": entry.state.value,
                "reason": friendly_reason,
            })

        return failed_entries

    def _get_trace_errors(self, domain: str, excluded: list) -> list:
        """Récupère les erreurs dans les traces d'automatisations ou de scripts avec horodatage."""
        trace_data = self.hass.data.get("trace", {})
        if not trace_data:
            return []

        # Récupération du registre des entités pour la correspondance des unique_id
        ent_reg = er.async_get(self.hass)
        failed = []

        for key, traces in list(trace_data.items()):
            # Filtrage par domaine (automation ou script)
            if not (key.startswith(f"{domain}.") or key.startswith(f"{domain} ")):
                continue
            if not traces:
                continue

            # Récupération de la dernière trace d'exécution
            try:
                trace_list = (
                    list(traces.values()) if isinstance(traces, dict) else list(traces)
                )
                if not trace_list:
                    continue
                latest_trace = trace_list[-1]
            except Exception:
                continue

            # 1. Extraction du dictionnaire de trace et du message d'erreur
            trace_dict = {}
            if hasattr(latest_trace, "as_dict"):
                try:
                    trace_dict = latest_trace.as_dict()
                except Exception:
                    trace_dict = {}
            elif isinstance(latest_trace, dict):
                trace_dict = latest_trace

            error_msg = trace_dict.get("error")
            if not error_msg and hasattr(latest_trace, "error"):
                error_msg = getattr(latest_trace, "error", None)

            # Si aucune erreur dans la dernière trace, on passe au suivant
            if not error_msg:
                continue

            # 2. Résolution de l'entity_id réel via l'Entity Registry
            entity_id = None
            raw_id = key.split(".", 1)[-1] if "." in key else key.split(" ", 1)[-1]

            # Cas A: La clé est déjà un entity_id valide (très fréquent pour les scripts)
            if key in self.hass.states.async_entity_ids(domain):
                entity_id = key
            else:
                # Cas B: Recherche dans le registre par unique_id (très fréquent pour les automatisations)
                for entry in ent_reg.entities.values():
                    if entry.domain == domain and (
                        entry.unique_id == raw_id or entry.entity_id == key
                    ):
                        entity_id = entry.entity_id
                        break

            # 3. Récupération du friendly_name et vérification des exclusions
            friendly_name = None

            if entity_id:
                if entity_id in excluded:
                    continue
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = (
                        state.attributes.get("friendly_name") or entity_id
                    )

            # Fallback si l'entité n'a pas été trouvée dans le registre
            friendly_name = friendly_name or key
            if friendly_name in excluded:
                continue

            # 4. Extraire la date/heure d'exécution
            error_time = None
            if hasattr(latest_trace, "start_time"):
                error_time = getattr(latest_trace, "start_time")

            if not error_time and trace_dict:
                ts_info = trace_dict.get("timestamp")
                if isinstance(ts_info, dict):
                    error_time = ts_info.get("start") or ts_info.get("finish")
                else:
                    error_time = trace_dict.get("start_time")

            formatted_date = _format_date_local(error_time)

            item = {
                "name": friendly_name,
                "entity_id": entity_id or key,
                "date": formatted_date,
                "error": str(error_msg),
            }

            # Évite les doublons dans la liste
            if not any(f["name"] == friendly_name for f in failed):
                failed.append(item)

        return failed

    async def _async_get_pending_repairs(self, excluded: list) -> list:
        """Récupère les réparations en attente avec leurs titres officiels traduits."""
        issue_registry = ir.async_get(self.hass)
        active_issues = [
            issue for issue in issue_registry.issues.values()
            if getattr(issue, "active", True) and getattr(issue, "dismissed_version", None) is None
        ]

        # 1. Récupération des domaines concernés
        domains = {issue.domain for issue in active_issues}

        # 2. Chargement des traductions officielles HA pour la catégorie 'issues'
        translations = {}
        if domains:
            try:
                translations = await async_get_translations(
                    self.hass,
                    self.hass.config.language,
                    "issues",
                    domains=domains,
                )
            except Exception:
                translations = {}

        pending = []
        for issue in active_issues:
            issue_identifier = f"{issue.domain}: {issue.issue_id}"
            if (
                excluded in issue_identifier
                or issue.domain in excluded
                or excluded in issue.issue_id
            ):
                continue

            # 3. Recherche du titre traduit dans le dictionnaire HA
            key_name = getattr(issue, "translation_key", None) or issue.issue_id
            trans_key = f"component.{issue.domain}.issues.{key_name}.title"

            friendly_name = None
            if trans_key in translations:
                raw_title = translations[trans_key]
                # Injection des variables si l'alerte contient des placeholders (ex: nom d'entité, version...)
                placeholders = getattr(issue, "translation_placeholders", None)
                if placeholders and isinstance(placeholders, dict):
                    try:
                        friendly_name = raw_title.format(**placeholders)
                    except Exception:
                        friendly_name = raw_title
                else:
                    friendly_name = raw_title

            # 4. Fallback propre si aucune traduction n'est trouvée
            if not friendly_name:
                domain_friendly = issue.domain.replace("_", " ").title()
                issue_friendly = key_name.replace("_", " ").capitalize()
                friendly_name = f"{domain_friendly} — {issue_friendly}"

            # 5. Date / heure
            created_at = getattr(issue, "created", None)
            formatted_date = _format_date_local(created_at)

            repair_item = {
                "name": friendly_name,
                "domain": issue.domain,
                "date": formatted_date,
                "issue_id": issue.issue_id,
            }

            if repair_item not in pending:
                pending.append(repair_item)

        return pending