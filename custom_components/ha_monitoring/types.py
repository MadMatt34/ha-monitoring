"""Définitions des types et structures de données pour HA Monitoring."""

from typing import TypedDict


class MonitoringBackupData(TypedDict):
    """Structure des données pour l'état des sauvegardes."""

    is_ok: bool
    date_last_run: str | None
    date_last_success: str | None
    date_next_schedule: str | None
    size: str | None
    failure: str | None
    failed_agents: list[str]
    failed_addons: list[str]
    failed_folders: list[str]
    current_agent_errors: dict[str, str]


class RecorderData(TypedDict, total=False):
    """Structure des métriques Recorder/base de données."""

    recorder_keep_days: int | None
    recorder_auto_purge: bool | None
    recorder_auto_repack: bool | None
    recorder_commit_interval: int | None
    database_size_mb: float | None


class SystemStatsData(RecorderData, total=False):
    """Structure des statistiques système."""

    ha_version: str
    ha_last_boot: str
    os_version: str
    os_last_boot: str
    devices_count: int
    entities_count: int
    automations_count: int
    scripts_count: int
    integrations_count: int
    custom_integrations_count: int


class UpdateEntityData(TypedDict):
    """Structure d'une mise à jour disponible."""

    entity_id: str
    name: str
    installed_version: str
    latest_version: str


class UnavailableEntityData(TypedDict):
    """Structure d'une entité indisponible."""

    entity_id: str
    name: str
    domain: str
    state: str


class OfflineDeviceData(TypedDict):
    """Structure d'un appareil hors ligne."""

    device: str
    date: str
    platform: str


class FailedIntegrationData(TypedDict):
    """Structure d'une intégration en erreur."""

    name: str
    entry_name: str
    domain: str
    entry_id: str
    state: str
    reason: str


class PendingRepairData(TypedDict):
    """Structure d'une réparation en attente."""

    name: str
    domain: str
    date: str
    issue_id: str


class TraceErrorData(TypedDict):
    """Structure d'une erreur de trace."""

    name: str
    entity_id: str
    date: str
    error: str


class MonitoringAddonData(TypedDict):
    """Données du capteur Add-ons."""

    items: list[str]
    total: int


class MonitoringIntegrationData(TypedDict):
    """Données du capteur Intégrations."""

    items: list[FailedIntegrationData]
    total: int


class MonitoringTraceData(TypedDict):
    """Données d'un capteur de traces."""

    items: list[TraceErrorData]
    total: int


class MonitoringUpdateData(TypedDict):
    """Données du capteur des mises à jour."""

    items: list[UpdateEntityData]
    total: int


class MonitoringRepairData(TypedDict):
    """Données du capteur des réparations."""

    items: list[PendingRepairData]
    total: int


class MonitoringUnavailableData(TypedDict):
    """Données du capteur des entités indisponibles."""

    items: list[UnavailableEntityData]
    total: int


class MonitoringOfflineData(TypedDict):
    """Données du capteur des appareils hors ligne."""

    items: list[OfflineDeviceData]
    total: int
    timeout: float


class HAMonitoringData(TypedDict):
    """Structure complète produite par le Coordinator."""

    startup_delay: bool
    system_stats: SystemStatsData
    monitoring_addons: MonitoringAddonData
    monitoring_integrations: MonitoringIntegrationData
    monitoring_automations: MonitoringTraceData
    monitoring_scripts: MonitoringTraceData
    monitoring_updates: MonitoringUpdateData
    monitoring_repairs: MonitoringRepairData
    monitoring_unavailable: MonitoringUnavailableData
    monitoring_offline: MonitoringOfflineData
    monitoring_backup: MonitoringBackupData
