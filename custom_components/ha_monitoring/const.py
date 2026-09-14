"""Constantes pour l'intégration HA Monitoring."""

from homeassistant.config_entries import ConfigEntryState

DOMAIN = "ha_monitoring"
DEVICE_NAME = "Home Assistant"
DEVICE_MANUFACTURER = "Home Assistant Community"

# Paramètres de configuration
CONF_STARTUP_DELAY = "startup_delay"
DEFAULT_STARTUP_DELAY = 120

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 180

CONF_SYSTEM_INFO_SCAN_INTERVAL = "system_info_scan_interval"
DEFAULT_SYSTEM_INFO_SCAN_INTERVAL = 24

CONF_TRACES_SCAN_INTERVAL = "traces_scan_interval"
DEFAULT_TRACES_SCAN_INTERVAL = 30

CONF_OFFLINE_TIMEOUT = "offline_timeout"
DEFAULT_OFFLINE_TIMEOUT = 24

CONF_BATTERY_LOW_THRESHOLD = "battery_low_threshold"
DEFAULT_BATTERY_LOW_THRESHOLD = 15

# Clés d'exclusions
CONF_EXCLUDED_ADDONS = "excluded_addons"
CONF_EXCLUDED_INTEGRATIONS = "excluded_integrations"
CONF_EXCLUDED_AUTOMATIONS = "excluded_automations"
CONF_EXCLUDED_SCRIPTS = "excluded_scripts"
CONF_EXCLUDED_UPDATES = "excluded_updates"
CONF_EXCLUDED_REPAIRS = "excluded_repairs"
CONF_EXCLUDED_OFFLINE = "excluded_offline"
CONF_EXCLUDED_UNAVAILABLE_ENTITIES = "excluded_unavailable_entities"
CONF_EXCLUDED_UNAVAILABLE_GLOBS = "excluded_unavailable_globs"
CONF_EXCLUDED_UNAVAILABLE_DOMAINS = "excluded_unavailable_domains"
CONF_EXCLUDED_BATTERIES = "excluded_batteries"

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
ICON_MAINTENANCE = "mdi:wrench-clock"
ICON_BATTERY = "mdi:battery-alert"

# Identifiants uniques
UNIQUE_ID_ADDONS = "monitoring_applications"
UNIQUE_ID_INTEGRATIONS = "monitoring_integrations"
UNIQUE_ID_AUTOMATIONS = "monitoring_automations"
UNIQUE_ID_SCRIPTS = "monitoring_scripts"
UNIQUE_ID_STATUS = "monitoring_global_status"
UNIQUE_ID_UPDATES = "monitoring_updates"
UNIQUE_ID_REPAIRS = "monitoring_repairs"
UNIQUE_ID_UNAVAILABLE = "monitoring_unavailable_entities"
UNIQUE_ID_OFFLINE = "monitoring_offline_devices"
UNIQUE_ID_BACKUP = "monitoring_backup"
UNIQUE_ID_REFRESH = "monitoring_force_scan"
UNIQUE_ID_MAINTENANCE = "monitoring_maintenance"
UNIQUE_ID_BATTERY = "monitoring_low_battery"

# Clés de traduction
TRANSLATION_KEY_ADDONS = "applications"
TRANSLATION_KEY_INTEGRATIONS = "integrations"
TRANSLATION_KEY_AUTOMATIONS = "automations"
TRANSLATION_KEY_SCRIPTS = "scripts"
TRANSLATION_KEY_STATUS = "global_status"
TRANSLATION_KEY_UPDATES = "updates"
TRANSLATION_KEY_REPAIRS = "repairs"
TRANSLATION_KEY_UNAVAILABLE = "unavailable_entities"
TRANSLATION_KEY_OFFLINE = "offline_devices"
TRANSLATION_KEY_BACKUP = "backup"
TRANSLATION_KEY_REFRESH = "force_scan"
TRANSLATION_KEY_MAINTENANCE = "maintenance"
TRANSLATION_KEY_BATTERY = "low_battery"

# Suffixes utilisés pour la détection Hors-ligne
DEFAULT_LAST_SEEN_SUFFIX = (
    "last_seen",
    "last_updated",
    "_last_seen",
    "_last_updated",
)

LOCALIZED_LAST_SEEN_SUFFIX: dict[str, str] = {
    "fr": "derniere_connexion",
    "en": "last_seen",
    "es": "ultima_conexion",
    "de": "letztes_gesehen",
}

# Attributs
ATTR_STARTUP_DELAY = "startup_delay"
ATTR_DATE_LAST_RUN = "date_last_run"
ATTR_DATE_LAST_SUCCESS = "date_last_success"
ATTR_DATE_NEXT_SCHEDULE = "date_next_schedule"
ATTR_SIZE = "size"
ATTR_FAILURE = "failure"
ATTR_TOTAL = "total"
ATTR_LIST = "list"
ATTR_MAINTENANCE = "maintenance"
ATTR_THRESHOLD = "threshold"

# Persistance
STORAGE_KEY_MAINTENANCE = f"{DOMAIN}.maintenance_mode"
STORAGE_VERSION_MAINTENANCE = 1

# États d'une ConfigEntry en erreur
INTEGRATION_ERROR_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.MIGRATION_ERROR,
    ConfigEntryState.FAILED_UNLOAD,
}

# États valides à comptabiliser
INTEGRATION_VALID_STATES = {
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.FAILED_UNLOAD,
    ConfigEntryState.SETUP_IN_PROGRESS,
}

# Domaines d'intégration à exclure du comptage
INTEGRATION_EXCLUDED_DOMAINS = {
    "group",
    "utility_meter",
    "threshold",
    "min_max",
    "template",
    "tod",
    "derivative",
    "integral",
    "compensation",
    "filter",
    "generic_thermostat",
    "generic_hygrostat",
    "timer",
    "counter",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "schedule",
    "bayesian",
    "trend",
    "go2rtc",
    "statistics",
    "switch_as_x",
    "hardware",
    "diagnostics",
    "analytics",
    "homeassistant",
    "integration",
}
