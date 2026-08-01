"""Constantes pour l'intégration HA Monitoring."""
from datetime import timedelta
from homeassistant.config_entries import ConfigEntryState

DOMAIN = "ha_monitoring"

# Paramètres de configuration
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # Secondes

CONF_OFFLINE_TIMEOUT = "offline_timeout"
DEFAULT_OFFLINE_TIMEOUT = 24  # Heures

CONF_STARTUP_DELAY = "startup_delay"
DEFAULT_STARTUP_DELAY = 180  # 180 secondes (3 minutes)

# Clés d'exclusions
CONF_EXCLUDED_ADDONS = "excluded_addons"
CONF_EXCLUDED_INTEGRATIONS = "excluded_integrations"
CONF_EXCLUDED_AUTOMATIONS = "excluded_automations"
CONF_EXCLUDED_SCRIPTS = "excluded_scripts"
CONF_EXCLUDED_UPDATES = "excluded_updates"
CONF_EXCLUDED_REPAIRS = "excluded_repairs"
CONF_EXCLUDED_UNAVAILABLE = "excluded_unavailable"
CONF_EXCLUDED_OFFLINE = "excluded_offline"

# Icônes MDI
ICON_ADDONS = "mdi:puzzle-remove-outline"
ICON_INTEGRATIONS = "mdi:alert-circle-outline"
ICON_AUTOMATIONS = "mdi:robot-dead"
ICON_SCRIPTS = "mdi:script-text-outline"
ICON_STATUS = "mdi:shield-alert"
ICON_UPDATES = "mdi:package-up"
ICON_REPAIRS = "mdi:screwdriver"
ICON_UNAVAILABLE = "mdi:ghost-outline"
ICON_OFFLINE = "mdi:wifi-off"
ICON_BACKUP = "mdi:backup-restore"

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

# Attributs
ATTR_ADDONS_EN_ERREUR = "addons_en_erreur"
ATTR_INTEGRATIONS_EN_ERREUR = "integrations_en_erreur"
ATTR_AUTOMATIONS_EN_ERREUR = "automations_en_erreur"
ATTR_SCRIPTS_EN_ERREUR = "scripts_en_erreur"
ATTR_MISES_A_JOUR_EN_ATTENTE = "mises_a_jour_en_attente"
ATTR_CORRECTIONS_EN_ATTENTE = "corrections_en_attente"
ATTR_ENTITES_INDISPONIBLES = "entites_indisponibles"
ATTR_APPAREILS_HORS_LIGNE = "appareils_hors_ligne"
ATTR_TOTAL_EN_ERREUR = "total_en_erreur"
ATTR_TOTAL_EN_ATTENTE = "total_en_attente"
ATTR_TOTAL_INDISPONIBLES = "total_indisponibles"
ATTR_TOTAL_HORS_LIGNE = "total_hors_ligne"

# Attributs Sauvegarde
ATTR_DATE_SAUVEGARDE = "date_sauvegarde"
ATTR_DATE_DERNIERE_REUSSIE = "date_derniere_reussie"
ATTR_DATE_PROCHAINE_PLANIFIEE = "date_prochaine_planifiee"
ATTR_TAILLE_SAUVEGARDE = "taille_sauvegarde"

# États d'erreur d'une ConfigEntry (Intégrations)
INTEGRATION_ERROR_STATES = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.MIGRATION_ERROR,
}
