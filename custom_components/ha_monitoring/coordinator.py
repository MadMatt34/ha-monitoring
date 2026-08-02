"""DataUpdateCoordinator centralisé et optimisé pour HA Monitoring."""
import logging
from datetime import datetime, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.loader import async_get_integration
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
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

# Attributs recherchés pour la date de dernière présence
LAST_SEEN_ATTRS = ("last_seen", "last_reported", "derniere_connexion", "last_seen_timestamp")


def is_hassio_running(hass: HomeAssistant) -> bool:
    """Vérifie si Home Assistant s'exécute sous Supervisor/Hassio."""
    return "hassio" in hass.config.components


class HAMonitoringCoordinator(DataUpdateCoordinator):
    """Coordinator principal gérant les collectes et la temporisation."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        self._boot_time = dt_util.utcnow()
        self._cached_backup_info = None

        # Cache pour les traces d'automatisations et scripts
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

        # Écoute des événements de fin de sauvegarde
        self._setup_backup_listeners()

    def _setup_backup_listeners(self) -> None:
        """Écoute les événements déclenchés à la fin d'une sauvegarde (Core et Supervisor)."""
        @callback
        async def _async_on_backup_event(event):
            _LOGGER.debug(
                "Fin de sauvegarde détectée via l'événement '%s'. Actualisation de l'état.",
                event.event_type,
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

    async def async_force_refresh(self) -> None:
        """Force la réinitialisation des caches, annule la temporisation de démarrage et rafraîchit immédiatement."""
        _LOGGER.debug("Réinitialisation de tous les caches et annulation de la temporisation pour scan forcé.")
        # On réinitialise l'heure de boot pour lever instantanément le délai de grâce au démarrage
        self._boot_time = dt_util.utcnow()
        self._last_trace_check_time = None
        self._cached_backup_info = None

        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Récupère les métriques système en optimisant le parcours des états."""
        startup_delay = self.entry.options.get(CONF_STARTUP_DELAY, DEFAULT_STARTUP_DELAY)
        now = dt_util.utcnow()
        elapsed_seconds = (now - self._boot_time).total_seconds()

        # Phase de démarrage
        in_startup_phase = (
            self.hass.state != CoreState.running or elapsed_seconds < startup_delay
        )

        # On s'assure d'initialiser les infos de sauvegarde dès le premier cycle, même au démarrage
        if self._cached_backup_info is None:
            self._cached_backup_info = await self._async_get_backup_info()

        if in_startup_phase:
            remaining = max(0, int(startup_delay - elapsed_seconds))
            _LOGGER.debug(
                "HA Monitoring en phase d'initialisation (%s s restantes). Alertes masquées.",
                remaining,
            )
            # On retourne les résultats masqués mais avec la vraie information de sauvegarde
            results = self._empty_results(in_startup_delay=True)
            results["monitoring_backup"] = self._cached_backup_info
            return results

        _LOGGER.debug("Analyse système optimisée active par HA Monitoring.")

        options = self.entry.options
        offline_timeout = options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)

        # 1. Parcours UNIQUE du registre d'états (Updates, Unavailable, Offline)
        updates, unavailable, offline = self._scan_all_states(
            excluded_updates=options.get(CONF_EXCLUDED_UPDATES, []),
            excluded_unavailable=options.get(CONF_EXCLUDED_UNAVAILABLE, []),
            excluded_offline=options.get(CONF_EXCLUDED_OFFLINE, []),
            timeout_hours=offline_timeout,
        )

        # 2. Analyse temporisée des traces d'automatisations & scripts (par défaut toutes les 15 min)
        traces_scan_interval_min = options.get(
            CONF_TRACES_SCAN_INTERVAL, DEFAULT_TRACES_SCAN_INTERVAL
        )
        traces_scan_interval_sec = float(traces_scan_interval_min) * 60

        if (
            self._last_trace_check_time is None
            or (now - self._last_trace_check_time).total_seconds() >= traces_scan_interval_sec
        ):
            _LOGGER.debug("Actualisation des traces d'automatisations et de scripts.")
            self._cached_automations = self._get_trace_errors(
                "automation", options.get(CONF_EXCLUDED_AUTOMATIONS, [])
            )
            self._cached_scripts = self._get_trace_errors(
                "script", options.get(CONF_EXCLUDED_SCRIPTS, [])
            )
            self._last_trace_check_time = now

        # 3. Collectes secondaires hors registre d'états
        addons = await self._async_get_addons(options.get(CONF_EXCLUDED_ADDONS, []))
        integrations = self._get_failed_integrations(options.get(CONF_EXCLUDED_INTEGRATIONS, []))
        repairs = self._get_pending_repairs(options.get(CONF_EXCLUDED_REPAIRS, []))

        # 4. Chargement de la sauvegarde si non encore mise en cache
        if self._cached_backup_info is None:
            self._cached_backup_info = await self._async_get_backup_info()

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
        now = dt_util.now()
        cutoff = now - timedelta(hours=float(timeout_hours))

        updates = []
        unavailable = []
        offline = []

        for state_obj in self.hass.states.async_all():
            entity_id = state_obj.entity_id
            friendly_name = state_obj.attributes.get("friendly_name") or entity_id

            # A. Entités Indisponibles
            if state_obj.state == STATE_UNAVAILABLE:
                if entity_id not in excluded_unavailable and friendly_name not in unavailable:
                    unavailable.append(friendly_name)
                continue

            # B. Mises à jour en attente (Domaine update)
            if entity_id.startswith("update."):
                if (
                    entity_id not in excluded_updates
                    and state_obj.state == "on"
                    and friendly_name not in updates
                ):
                    updates.append(friendly_name)
                continue

            # C. Appareils hors ligne (Strictement basés sur la terminaison de l'entity_id)
            if entity_id.endswith(("last_seen", "derniere_connexion")):
                if entity_id in excluded_offline or state_obj.state in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    continue

                last_seen_dt = None

                # Essai de parsing direct de l'état
                last_seen_dt = dt_util.parse_datetime(str(state_obj.state))

                # Si l'état n'est pas une date valide, recherche dans les attributs connus
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

                # Vérification du dépassement de délai
                if last_seen_dt and dt_util.as_utc(last_seen_dt) < dt_util.as_utc(cutoff):
                    if friendly_name not in offline:
                        offline.append(friendly_name)

        return updates, unavailable, offline

    def _empty_results(self, in_startup_delay: bool) -> dict:
        """Résultats neutres pendant la temporisation de démarrage."""
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

    def _format_size(self, size_bytes_or_mb) -> str | None:
        """Formate la taille en Mo ou Go."""
        if size_bytes_or_mb is None:
            return None

        if isinstance(size_bytes_or_mb, (int, float)):
            if size_bytes_or_mb > 1024 * 1024:
                mb = size_bytes_or_mb / (1024 * 1024)
            else:
                mb = size_bytes_or_mb

            if mb >= 1024:
                return f"{round(mb / 1024, 2)} Go"
            return f"{round(mb, 2)} Mo"
        return str(size_bytes_or_mb)

    async def _async_get_backup_info(self) -> dict:
        """Interroge le gestionnaire de sauvegardes Supervisor ou Core."""
        backups_list = []
        next_scheduled = None

        # 1. Tentative via l'API Supervisor / HASSIO
        if is_hassio_running(self.hass):
            try:
                client = self.hass.data.get("hassio")
                if client:
                    backups_info = None
                    if hasattr(client, "async_get_backups"):
                        backups_info = await client.async_get_backups()
                    elif hasattr(client, "get_backups"):
                        backups_info = await client.get_backups()
                    elif hasattr(client, "send_command"):
                        backups_info = await client.send_command("/backups", method="get")

                    if isinstance(backups_info, dict) and "backups" in backups_info:
                        backups_list = backups_info.get("backups", [])
            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Hassio : %s", err)

        # 2. Fallback via le module Backup natif de Home Assistant Core
        if not backups_list and "backup" in self.hass.data:
            try:
                backup_manager = self.hass.data["backup"]
                if hasattr(backup_manager, "backups"):
                    raw_backups = backup_manager.backups
                    if isinstance(raw_backups, dict):
                        for b in raw_backups.values():
                            backups_list.append({
                                "slug": getattr(b, "slug", None) or getattr(b, "id", ""),
                                "name": getattr(b, "name", ""),
                                "date": getattr(b, "date", None),
                                "size": getattr(b, "size", 0),
                                "failed": getattr(b, "failed", False),
                                "reason": getattr(b, "reason", None) or getattr(b, "error", None),
                            })

                if hasattr(backup_manager, "config") and hasattr(backup_manager.config, "create_backup"):
                    schedule = getattr(backup_manager.config, "schedule", None)
                    if schedule and hasattr(schedule, "next_execution"):
                        next_scheduled = schedule.next_execution
            except Exception as err:
                _LOGGER.debug("Erreur récupération sauvegardes via Backup Core : %s", err)

        if not backups_list:
            return {
                "is_ok": False,
                "date_sauvegarde": None,
                "date_derniere_reussie": None,
                "date_prochaine_planifiee": str(next_scheduled) if next_scheduled else "Non configurée",
                "taille_sauvegarde": None,
                "reason_failed": "Aucune sauvegarde disponible",
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

        reason_failed = None
        if is_failed:
            reason_failed = (
                latest_backup.get("reason")
                or latest_backup.get("error")
                or latest_backup.get("failure_reason")
                or "Raison d'échec inconnue"
            )

        last_dt = get_date(latest_backup)
        date_sauvegarde = (
            last_dt.isoformat()
            if last_dt != datetime.min.replace(tzinfo=dt_util.UTC)
            else str(latest_backup.get("date"))
        )

        last_successful_dt = None
        for b in sorted_backups:
            if not b.get("failed", False) and b.get("status") != "failed":
                last_successful_dt = get_date(b)
                break

        if last_successful_dt and last_successful_dt != datetime.min.replace(tzinfo=dt_util.UTC):
            date_derniere_reussie = last_successful_dt.isoformat()
        else:
            date_derniere_reussie = date_sauvegarde if is_ok else "Aucune"

        if next_scheduled:
            if isinstance(next_scheduled, datetime):
                date_prochaine_planifiee = next_scheduled.isoformat()
            else:
                date_prochaine_planifiee = str(next_scheduled)
        else:
            date_prochaine_planifiee = "Non planifiée"

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
        """Récupère la liste des add-ons en état anormal."""
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
        """Récupère le nom officiel des intégrations en état d'erreur de chargement."""
        failed = []
        for entry in self.hass.config_entries.async_entries():
            if entry.state in INTEGRATION_ERROR_STATES:
                # Vérification directe de l'exclusion du domaine technique (ex: "hue")
                if entry.domain in excluded:
                    continue

                # Récupération du nom officiel de l'intégration (ex: "Philips Hue")
                try:
                    integration = await async_get_integration(self.hass, entry.domain)
                    integration_name = integration.name
                except Exception:
                    integration_name = entry.domain.replace("_", " ").title()

                # Vérification si le nom d'affichage est exclu ou déjà présent dans la liste
                if integration_name not in excluded and integration_name not in failed:
                    failed.append(integration_name)

        return failed

    def _get_trace_errors(self, domain: str, excluded: list) -> list:
        """Extrait les erreurs des traces d'automatisations ou de scripts."""
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
        """Récupère la liste des réparations en attente."""
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
