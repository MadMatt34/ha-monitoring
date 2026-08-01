"""Constantes pour l'intégration HA Monitoring."""
from datetime import timedelta
from homeassistant.config_entries import ConfigEntryState

DOMAIN = "ha_monitoring"

# Paramètres de configuration
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # Secondes

# Icônes MDI
ICON_ADDONS = "mdi:puzzle-alert"
ICON_INTEGRATIONS = "mdi:alert-circle-outline"
ICON_AUTOMATIONS = "mdi:robot-dead"
ICON_SCRIPTS = "mdi:script-text-outline"
ICON_STATUS = "mdi:shield-alert"
ICON_UPDATES = "mdi:package-up"
ICON_REPAIRS = "mdi:wrench-alert"
ICON_UNAVAILABLE = "mdi:ghost-outline"  # <--- Nouveau

# Identifiants uniques
UNIQUE_ID_ADDONS = "ha_monitoring_addons_in_error_sensor"
UNIQUE_ID_INTEGRATIONS = "ha_monitoring_integrations_in_error_sensor"
UNIQUE_ID_AUTOMATIONS = "ha_monitoring_automations_in_error"
UNIQUE_ID_SCRIPTS = "ha_monitoring_scripts_in_error"
UNIQUE_ID_STATUS = "ha_monitoring_status"
UNIQUE_ID_UPDATES = "ha_monitoring_updates_pending_sensor"
UNIQUE_ID_REPAIRS = "ha_monitoring_repairs_pending_sensor"
UNIQUE_ID_UNAVAILABLE = "ha_monitoring_unavailable_entities_sensor"  # <--- Nouveau

# Clés de traduction
TRANSLATION_KEY_ADDONS = "addons_in_error"
TRANSLATION_KEY_INTEGRATIONS = "integrations_in_error"
TRANSLATION_KEY_AUTOMATIONS = "automations_in_error"
TRANSLATION_KEY_SCRIPTS = "scripts_in_error"
TRANSLATION_KEY_STATUS = "global_status"
TRANSLATION_KEY_UPDATES = "updates_pending"
TRANSLATION_KEY_REPAIRS = "repairs_pending"
TRANSLATION_KEY_UNAVAILABLE = "unavailable_entities"  # <--- Nouveau

# Attributs
ATTR_ADDONS_EN_ERREUR = "addons_en_erreur"
ATTR_INTEGRATIONS_EN_ERREUR = "integrations_en_erreur"
ATTR_AUTOMATIONS_EN_ERREUR = "automations_en_erreur"
ATTR_SCRIPTS_EN_ERREUR = "scripts_en_erreur"
ATTR_MISES_A_JOUR_EN_ATTENTE = "mises_a_jour_en_attente"
ATTR_CORRECTIONS_EN_ATTENTE = "corrections_en_attente"
ATTR_ENTITES_INDISPONIBLES = "entites_indisponibles"  # <--- Nouveau
ATTR_TOTAL_EN_ERREUR = "total_en_erreur"
ATTR_TOTAL_EN_ATTENTE = "total_en_attente"
ATTR_TOTAL_INDISPONIBLES = "total_indisponibles"  # <--- Nouveau

# États d'erreur d'une ConfigEntry (Intégrations)
INTEGRATION_ERROR_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.MIGRATION_ERROR,
}
