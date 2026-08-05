"""Constantes pour l'intégration HA Monitoring."""
from datetime import timedelta
from homeassistant.config_entries import ConfigEntryState

DOMAIN = "ha_monitoring"
DEVICE_NAME = "Home Assistant"
DEVICE_MANUFACTURER = "Home Assistant Community"

# Paramètres de configuration
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 120  # en secondes

CONF_TRACES_SCAN_INTERVAL = "traces_scan_interval"
DEFAULT_TRACES_SCAN_INTERVAL = 30  # en minutes

CONF_OFFLINE_TIMEOUT = "offline_timeout"
DEFAULT_OFFLINE_TIMEOUT = 24  # en heures

CONF_STARTUP_DELAY = "startup_delay"
DEFAULT_STARTUP_DELAY = 120  # en secondes

# Clés d'exclusions
CONF_EXCLUDED_ADDONS = "excluded_addons"
CONF_EXCLUDED_INTEGRATIONS = "excluded_integrations"
CONF_EXCLUDED_AUTOMATIONS = "excluded_automations"
CONF_EXCLUDED_SCRIPTS = "excluded_scripts"
CONF_EXCLUDED_UPDATES = "excluded_updates"
CONF_EXCLUDED_REPAIRS = "excluded_repairs"
CONF_EXCLUDED_OFFLINE = "excluded_offline"
CONF_EXCLUDED_UNAVAILABLE_ENTITIES = "excluded_unavailable_entities"
CONF_EXCLUDED_UNAVAILABLE_DOMAINS = "excluded_unavailable_domains"
# Domaines indésirables masqués par défaut
DEFAULT_EXCLUDED_UNAVAILABLE_DOMAINS = [
    "assist_satellite",
    "automation",
    "button",
    "conversation",
    "device_tracker",
    "infrared",
    "media_player",
    "notify",
    "person",
    "remote",
    "script",
    "siren",
    "stt",
    "tts",
    "update",
]

# Icônes MDI
ICON_ADDONS = "mdi:puzzle-remove-outline"
ICON_INTEGRATIONS = "mdi:alert-circle-outline"
ICON_AUTOMATIONS = "mdi:robot-dead"
ICON_SCRIPTS = "mdi:script-text-outline"
ICON_STATUS = "mdi:shield-alert"
ICON_UPDATES = "mdi:package-up"
ICON_REPAIRS = "mdi:screwdriver"
ICON_UNAVAILABLE = "mdi:ghost-outline"
ICON_OFFLINE = "mdi:link-variant-off"
ICON_BACKUP = "mdi:backup-restore"
ICON_REFRESH = "mdi:refresh"

# Identifiants uniques
UNIQUE_ID_ADDONS = "monitoring_applications_in_error"
UNIQUE_ID_INTEGRATIONS = "monitoring_integrations_in_error"
UNIQUE_ID_AUTOMATIONS = "monitoring_automations_in_error"
UNIQUE_ID_SCRIPTS = "monitoring_scripts_in_error"
UNIQUE_ID_STATUS = "monitoring_global_status"
UNIQUE_ID_UPDATES = "monitoring_updates_pending"
UNIQUE_ID_REPAIRS = "monitoring_repairs_pending"
UNIQUE_ID_UNAVAILABLE = "monitoring_unavailable_entities"
UNIQUE_ID_OFFLINE = "monitoring_offline_devices"
UNIQUE_ID_BACKUP = "monitoring_backup_status"
UNIQUE_ID_REFRESH = "monitoring_force_scan"

# Clés de traduction
TRANSLATION_KEY_ADDONS = "addons_in_error"
TRANSLATION_KEY_INTEGRATIONS = "integrations_in_error"
TRANSLATION_KEY_AUTOMATIONS = "automations_in_error"
TRANSLATION_KEY_SCRIPTS = "scripts_in_error"
TRANSLATION_KEY_STATUS = "global_status"
TRANSLATION_KEY_UPDATES = "updates_pending"
TRANSLATION_KEY_REPAIRS = "repairs_pending"
TRANSLATION_KEY_UNAVAILABLE = "unavailable_entities"
TRANSLATION_KEY_OFFLINE = "offline_devices"
TRANSLATION_KEY_BACKUP = "backup_status"
TRANSLATION_KEY_REFRESH = "force_scan"

# Suffixes et clés d'attributs utilisés pour la détection Hors-ligne
DEFAULT_LAST_SEEN_ATTRS = (
    "last_seen",
    "last_updated",
    "_last_seen",
    "_last_updated",
)

# Attributs
ATTR_STARTUP_DELAY = "startup_delay"
ATTR_DATE_LAST_RUN = "date_last_run"
ATTR_DATE_LAST_SUCCESS = "date_last_success"
ATTR_DATE_NEXT_SCHEDULE = "date_next_schedule"
ATTR_SIZE = "size"
ATTR_FAILURE = "failure"
ATTR_TOTAL = "total"
ATTR_LIST = "list"

# États d'erreur d'une ConfigEntry (Intégrations)
INTEGRATION_ERROR_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.MIGRATION_ERROR,
}
