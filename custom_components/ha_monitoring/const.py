"""Constantes pour l'intégration HA Monitoring."""
from datetime import timedelta
from homeassistant.config_entries import ConfigEntryState

DOMAIN = "ha_monitoring"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# Icônes MDI
ICON_ADDONS = "mdi:puzzle-alert"
ICON_INTEGRATIONS = "mdi:alert-circle-outline"
ICON_AUTOMATIONS = "mdi:robot-dead"
ICON_SCRIPTS = "mdi:script-text-outline"

# Identifiants uniques (Unique IDs)
UNIQUE_ID_ADDONS = "ha_monitoring_addons_in_error_sensor"
UNIQUE_ID_INTEGRATIONS = "ha_monitoring_integrations_in_error_sensor"
UNIQUE_ID_AUTOMATIONS = "ha_monitoring_automations_in_error"
UNIQUE_ID_SCRIPTS = "ha_monitoring_scripts_in_error"

# Clés de traduction (déclarées dans translations/fr.json)
TRANSLATION_KEY_ADDONS = "addons_in_error"
TRANSLATION_KEY_INTEGRATIONS = "integrations_in_error"
TRANSLATION_KEY_AUTOMATIONS = "automations_in_error"
TRANSLATION_KEY_SCRIPTS = "scripts_in_error"

# Noms des attributs d'état
ATTR_ADDONS_EN_ERREUR = "addons_en_erreur"
ATTR_INTEGRATIONS_EN_ERREUR = "integrations_en_erreur"
ATTR_AUTOMATIONS_EN_ERREUR = "automations_en_erreur"
ATTR_SCRIPTS_EN_ERREUR = "scripts_en_erreur"
ATTR_TOTAL_EN_ERREUR = "total_en_erreur"

# États d'erreur d'une ConfigEntry (Intégrations)
INTEGRATION_ERROR_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.MIGRATION_ERROR,
}
