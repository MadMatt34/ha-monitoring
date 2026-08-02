"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""
import logging
from datetime import datetime, timedelta, time

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDED_ADDONS,
    CONF_EXCLUDED_AUTOMATIONS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_EXCLUDED_OFFLINE,
    CONF_EXCLUDED_REPAIRS,
    CONF_EXCLUDED_SCRIPTS,
    CONF_EXCLUDED_UNAVAILABLE,
    CONF_EXCLUDED_UPDATES,
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

# Attributs de secours au cas où l'état ne soit pas directement parsable
LAST_SEEN_ATTRS = ("last_seen", "last_reported", "derniere_connexion", "last_seen_timestamp")


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


def _format_date_local(val) -> str | None:
    """Convertit un datetime ou une chaîne de date au format ISO avec le fuseau horaire local."""
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
        self._boot_time = dt_util.utcnow()
        self._cached_backup_info = None
        self._last_backup_failure_reason = None
        self._startup_timer_unsub = None

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
            self.hass.bus.async_listen(event_type, _async_on_backup_event)

    async def async_shutdown(self) -> None:
        """Libère les ressources."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None
        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Force le rafraîchissement immédiat de toutes les données."""
        if self._startup_timer_unsub:
            self._startup_timer_unsub()
            self._startup_timer_unsub = None

        self._boot_time = dt_util.utcnow() - timedelta(seconds=9999)
        self._last_trace_check_time = None
        self._cached_backup_info = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Récupère les métriques système."""
        startup_delay = float(self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY))
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._boot_time).total_seconds()

        in_startup_phase = (
            self.hass.state != CoreState.running or elapsed_seconds < (startup_delay - 0.5)
        )

        if self._cached_backup_info is None:
            self._cached_backup_info = await self._async_get_backup_info()

        if in_startup_phase:
            remaining = max(0.0, startup_delay - elapsed_seconds)
            
            if not self._startup_timer_unsub and remaining > 0:
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

        updates, unavailable, offline = self._scan_all_states(
            excluded_updates=options.get(CONF_EXCLUDED_UPDATES, []),
            excluded_unavailable=options.get(CONF_EXCLUDED_UNAVAILABLE, []),
            excluded_offline=options.get(CONF_EXCLUDED_OFFLINE, []),
            timeout_hours=offline_timeout,
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
        repairs = self._get_pending_repairs(options.get(CONF_EXCLUDED_REPAIRS, []))

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
        excluded_unavailable: list,
        excluded_offline: list,
        timeout_hours: float,
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
            friendly_name = state_obj.attributes.get("friendly_name") or entity_id

            if state_obj.state in (STATE_UNAVAILABLE):
                if entity_id not in excluded_unavailable:
                    unavailable.append(
                        {
                            "entity_id": entity_id,
                            "name": friendly_name,
                            "domain": state_obj.domain,
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

            if entity_id.endswith(("last_seen", "derniere_connexion")):
                if entity_id in excluded_offline or state_obj.state in (
                    STATE_UNAVAILABLE
                ):
                    continue

                last_seen_dt = dt_util.parse_datetime(str(state_obj.state))

                if not last_seen_dt and state_obj.attributes:
                    attrs = state_obj.attributes
                    for attr_key in LAST_SEEN_ATTRS:
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
                    if last_seen_dt.tzinfo is None:
                        last_seen_dt = (
                            dt_util.utc_from_timestamp(last_seen_dt.timestamp())
                            if hasattr(last_seen_dt, "timestamp")
                            else dt_util.as_utc(last_seen_dt)
                        )
                    else:
                        last_seen_dt = dt_util.as_utc(last_seen_dt)

                if last_seen_dt and last_seen_dt < cutoff:
                    device_name = None
                    platform = "inconnu"

                    entity_entry = ent_reg.async_get(entity_id)
                    if entity_entry:
                        platform = entity_entry.platform or "inconnu"
                        if entity_entry.device_id:
                            device_entry = dev_reg.async_get(entity_entry.device_id)
                            if device_entry:
                                device_name = device_entry.name_by_user or device_entry.name

                    display_name = device_name or friendly_name

                    if display_name not in excluded_offline and entity_id not in excluded_offline:
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
                "date_sauvegarde": None,
                "date_derniere_reussie": None,
                "date_prochaine_planifiee": "Démarrage...",
                "taille_sauvegarde": None,
                "reason_failed": None,
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
        """Calcule la date de la prochaine sauvegarde en fonction de la configuration HA Core."""
        try:
            state_str = str(schedule_state).split('.')[-1].lower()
            if not state_str or state_str == "never":
                return None
                
            now = dt_util.now()
            
            # Extraction propre de l'heure
            if isinstance(schedule_time_obj, time):
                h, m = schedule_time_obj.hour, schedule_time_obj.minute
            elif hasattr(schedule_time_obj, "hour") and hasattr(schedule_time_obj, "minute"):
                h, m = schedule_time_obj.hour, schedule_time_obj.minute
            else:
                parts = str(schedule_time_obj).split(":")
                h, m = int(parts[0]), int(parts[1])
                
            target_time = time(hour=h, minute=m)
            target_dt = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)
            
            # Planification journalière
            if state_str == "daily":
                if now >= target_dt:
                    target_dt += timedelta(days=1)
                return target_dt
                
            # Planification hebdomadaire
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
            _LOGGER.debug("Erreur HA Monitoring calcul prochaine sauvegarde : %s", err)
            
        return None

    async def _async_get_backup_info(self) -> dict:
        """Interroge le gestionnaire de sauvegardes Supervisor ou Core."""
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

                # Recherche approfondie du planning via l'API HA Core Native
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
                            # Calcul de la prochaine occurrence
                            next_scheduled = self._calculate_next_backup(state, time_val)
                    except Exception as err:
                        _LOGGER.debug("Erreur async_get_config backup : %s", err)

            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Backup Core : %s", err)

        # Filet de sécurité: Recherche dans les modules tiers (ex: HA Google Drive Backup ou Samba)
        if not next_scheduled:
            for sensor_id in ("sensor.backup_state", "sensor.samba_backup"):
                state = self.hass.states.get(sensor_id)
                if state and state.attributes:
                    next_val = state.attributes.get("next_backup")
                    if next_val:
                        next_scheduled = next_val
                        break

        if not backups_list:
            return {
                "is_ok": False,
                "date_sauvegarde": None,
                "date_derniere_reussie": None,
                "date_prochaine_planifiee": _format_date_local(next_scheduled) if next_scheduled else "Non configurée",
                "taille_sauvegarde": None,
                "reason_failed": self._last_backup_failure_reason or "Aucune sauvegarde disponible",
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

        reason_failed = self._last_backup_failure_reason
        if is_failed:
            reason_failed = (
                latest_backup.get("reason")
                or latest_backup.get("error")
                or latest_backup.get("failure_reason")
                or self._last_backup_failure_reason
                or "Raison d'échec inconnue"
            )
            self._last_backup_failure_reason = reason_failed

        last_dt = get_date(latest_backup)
        date_sauvegarde = _format_date_local(last_dt) if last_dt != datetime.min.replace(tzinfo=dt_util.UTC) else _format_date_local(latest_backup.get("date"))

        last_successful_dt = None
        for b in sorted_backups:
            if not b.get("failed", False) and b.get("status") != "failed":
                last_successful_dt = get_date(b)
                break

        if last_successful_dt and last_successful_dt != datetime.min.replace(tzinfo=dt_util.UTC):
            date_derniere_reussie = _format_date_local(last_successful_dt)
        else:
            date_derniere_reussie = date_sauvegarde if is_ok else "Aucune"

        date_prochaine_planifiee = _format_date_local(next_scheduled) if next_scheduled else "Non planifiée"
        taille_sauvegarde = self._format_size(latest_backup.get("size"))

        return {
            "is_ok": is_ok,
            "date_sauvegarde": date_sauvegarde,
            "date_derniere_reussie": date_derniere_reussie,
            "date_prochaine_planifiee": date_prochaine_planifiee,
            "taille_sauvegarde": taille_sauvegarde,
            "reason_failed": reason_failed,
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
        failed = []
        for entry in self.hass.config_entries.async_entries():
            if entry.state in INTEGRATION_ERROR_STATES:
                if entry.domain in excluded:
                    continue
                try:
                    integration = await async_get_integration(self.hass, entry.domain)
                    integration_name = integration.name
                except Exception:
                    integration_name = entry.domain.replace("_", " ").title()

                if integration_name not in excluded and integration_name not in failed:
                    failed.append(integration_name)
        return failed

    def _get_trace_errors(self, domain: str, excluded: list) -> list:
        trace_data = self.hass.data.get("trace", {})
        failed = []

        for key, traces in list(trace_data.items()):
            if not (key.startswith(f"{domain}.") or key.startswith(f"{domain} ")):
                continue
            if not traces:
                continue

            try:
                trace_list = list(traces.values()) if isinstance(traces, dict) else list(traces)
                if not trace_list:
                    continue
                latest_trace = trace_list[-1]
            except Exception:
                continue

            error = (
                latest_trace.as_dict().get("error")
                if hasattr(latest_trace, "as_dict")
                else latest_trace.get("error")
                if isinstance(latest_trace, dict)
                else None
            )

            if error:
                entity_id = key if key.startswith(f"{domain}.") else None
                friendly_name = None

                if entity_id:
                    if entity_id in excluded:
                        continue
                    state = self.hass.states.get(entity_id)
                    if state:
                        friendly_name = state.attributes.get("friendly_name") or entity_id

                if not friendly_name:
                    for state in self.hass.states.async_all(domain):
                        item_id = state.attributes.get("id")
                        if item_id is not None and str(item_id) in key:
                            if state.entity_id in excluded:
                                friendly_name = "EXCLUDED"
                                break
                            friendly_name = state.attributes.get("friendly_name") or state.entity_id
                            break

                if friendly_name == "EXCLUDED":
                    continue

                friendly_name = friendly_name or key
                if friendly_name not in excluded and friendly_name not in failed:
                    failed.append(friendly_name)

        return failed

    def _get_pending_repairs(self, excluded: list) -> list:
        issue_registry = ir.async_get(self.hass)
        pending = []
        for issue in issue_registry.issues.values():
            if hasattr(issue, "active") and not issue.active:
                continue
            if getattr(issue, "dismissed_version", None) is not None:
                continue

            issue_name = f"{issue.domain}: {issue.issue_id}"
            if issue_name in excluded or issue.domain in excluded or issue.issue_id in excluded:
                continue
            if issue_name not in pending:
                pending.append(issue_name)
        return pending
