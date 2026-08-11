"""Définitions des types et structures de données pour HA Monitoring."""

from typing import TypedDict


class MonitoringBackupData(TypedDict, total=False):
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
    """Structure des métriques associées au Recorder/Base de données."""

    recorder_keep_days: int | None
    recorder_auto_purge: bool | None
    recorder_auto_repack: bool | None
    recorder_commit_interval: int | None
    database_size_mb: float | None


class SystemStatsData(RecorderData, total=False):
    """Structure générale des statistiques système et inventaires."""

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
    """Structure pour une mise à jour en attente."""

    entity_id: str
    name: str
    installed_version: str
    latest_version: str


class UnavailableEntityData(TypedDict):
    """Structure pour une entité indisponible."""

    entity_id: str
    name: str
    domain: str
    state: str


class OfflineDeviceData(TypedDict):
    """Structure pour un appareil hors-ligne."""

    device: str
    date: str
    platform: str


class FailedIntegrationData(TypedDict):
    """Structure pour une intégration en erreur."""

    name: str
    entry_name: str
    domain: str
    entry_id: str
    state: str
    reason: str


class PendingRepairData(TypedDict):
    """Structure pour une réparation (issue) en attente."""

    name: str
    domain: str
    date: str
    issue_id: str


class TraceErrorData(TypedDict):
    """Structure pour une erreur d'automatisation ou de script."""

    name: str
    entity_id: str
    date: str
    error: str


class HAMonitoringData(TypedDict, total=False):
    """Structure globale des données consolidées par le DataUpdateCoordinator."""

    system: SystemStatsData
    backup: MonitoringBackupData
    updates: list[UpdateEntityData]
    unavailable: list[UnavailableEntityData]
    offline: list[OfflineDeviceData]
    failed_integrations: list[FailedIntegrationData]
    failed_addons: list[str]
    repairs: list[PendingRepairData]
    automation_errors: list[TraceErrorData]
    script_errors: list[TraceErrorData]
