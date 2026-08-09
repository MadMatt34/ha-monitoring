# HA Monitoring - Custom Component for Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Component-blue.svg)](https://www.home-assistant.io/)
[![Latest Release](https://img.shields.io/github/v/release/MadMatt34/ha-monitoring?color=green)](https://github.com/MadMatt34/ha-monitoring/releases)

![HA Monitoring for Home Assistant](https://github.com/MadMatt34/ha-monitoring/blob/main/logo.png)

[🇫🇷 README en FRANÇAIS 🇫🇷](https://github.com/MadMatt34/ha-monitoring/blob/main/README.fr.md)

**HA Monitoring** is a custom integration for Home Assistant designed to monitor system health and status in real time. It centralizes the detection of issues across add-ons, integrations, automations, scripts, unavailable or unknown entities, offline devices, pending updates, active repair alerts, and backup statuses.

---

## 🚀 Main Features

- **Centralized Device ("Home Assistant"):** All entities (sensors, buttons, binary sensors) are linked to a single system device displaying the current HA Core version alongside a direct link to your instance.
- **Comprehensive Monitoring:**
  - **Applications (Add-ons) & Integrations:** Detection of components in failed/error states.
  - **Automation & Script Traces:** Detection of execution errors in recent trace logs.
  - **Entities & Devices:** Tracking of unavailable/unknown (`unavailable` / `unknown`) entities and inactive devices (`offline`).
  - **Updates & Repairs:** Real-time metrics for pending system updates and repair issues.
  - **Backups:** Monitoring of the latest backup status with size and timestamp attributes.
- **Startup Grace Period:** Prevents false alarms during Home Assistant's initial boot sequence.
- **Action Button:** Forces an immediate, on-demand refresh of all metrics.
- **Fine-grained UI Configuration:** Adjustable scan intervals and granular selection of items to exclude from monitoring.

---

## 🧩 Installation

### Option 1: Installation via HACS (recommended)

1. Open **HACS**.
2. Click the 3 dots in the top right corner > **Custom repositories**.
3. Add repository URL: `https://github.com/MadMatt34/ha-monitoring`
4. Select **Integration** as category and confirm.
5. Click **Download**, then restart Home Assistant.

### Option 2: Manual Installation

1. Download the latest release archive from the repository.
2. Copy the `ha_monitoring` directory into `/config/custom_components/`.
3. Restart Home Assistant to load the custom component.

---

## 🚀 Integration Configuration

Setup is **100% UI-based** in Home Assistant.

1. Navigate to **Settings** > **Devices & Services**.

   [![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)]([https://my.home-assistant.io/redirect/integrations/](https://my.home-assistant.io/redirect/integrations/))
2. Click **Add Integration** (bottom right).
3. Search for **HA Monitoring** and select it.
4. Enter initial configuration parameters (or keep defaults) and submit.

---

## 🛠️ Modifying Settings

Thresholds and exclusion rules can be updated at any time:

1. Go to **Settings** > **Devices & Services** > **HA Monitoring**.
2. Click **CONFIGURE** (gear icon).
3. Adjust desired parameters:
    - **Refresh interval** (in seconds): Main data update frequency (default: 2 min).
    - **Traces scan interval** (in minutes): Analysis interval for automation and script execution traces (default: 30 min).
    - **Offline inactivity threshold** (in hours): Inactivity duration before marking a device offline (default: 24h).
    - **Startup grace period** (in seconds): Time to bypass scanning after Home Assistant boots (default: 2 min).
    - **Exclusions**: Select entities, add-ons, integrations, automations, scripts, updates, or repairs to ignore.

---

## 📊 Provided Entities

All entities are linked to the **Home Assistant** system device:

### Sensors (`sensor.*`)

| Entity | Name | Description / Attributes |
| :--- | :--- | :--- |
| `sensor.monitoring_addons` | Monitoring Failed Add-ons | Count of add-ons currently in an error state. |
| `sensor.monitoring_integrations` | Monitoring Failed Integrations | Count of failed integrations. |
| `sensor.monitoring_automations` | Monitoring Failed Automations | Count of automations that raised execution errors. |
| `sensor.monitoring_scripts` | Monitoring Failed Scripts | Count of scripts that raised execution errors. |
| `sensor.monitoring_updates` | Monitoring Pending Updates | Count of pending software/component updates. |
| `sensor.monitoring_repairs` | Monitoring Pending Repairs | Count of active system repair issues. |
| `sensor.monitoring_unavailable_entities` | Monitoring Unavailable Entities | Count and list of unavailable or unknown entities. |
| `sensor.monitoring_offline_devices` | Monitoring Offline Devices | Count and list of inactive devices. |

> **Note:** Every sensor provides detailed list attributes containing structured data (names, IDs, timestamps) for detected issues.

### Binary Sensors (`binary_sensor.*`)

| Entity | Device Class | Name | Description |
| :--- | :--- | :--- | :--- |
| `binary_sensor.monitoring_global_status` | `problem` | Monitoring Global Status | Turns `ON` if at least one critical issue (add-on, integration, automation, or script) is detected. |
| `binary_sensor.monitoring_backup_status` | - | Monitoring Backup Status | Turns `OFF` if the last backup attempt failed or is missing. |

### Buttons (`button.*`)

| Entity | Name | Description |
| :--- | :--- | :--- |
| `button.monitoring_force_scan` | Monitoring Force Refresh | Instantly triggers a complete system scan across all metrics. |

---

## 💡 Automations & Dashboard Examples

### Example 1: Notification on System Issue

```yaml
alias: "Alert: System Issue Detected"
description: "Sends a mobile notification if a system issue occurs"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_global_status
    to: "on"
condition: []
action:
  - action: notify.notify
    data:
      title: "⚠️ HA Monitoring - System Alert"
      message: >
        Issue detected on your Home Assistant system:
        - Failed Add-ons: {{ states('sensor.monitoring_addons') }}
        - Failed Integrations: {{ states('sensor.monitoring_integrations') }}
        - Failed Automations: {{ states('sensor.monitoring_automations') }}
        - Unavailable Entities: {{ states('sensor.monitoring_unavailable_entities') }}
mode: single
```

---

### Example 2: Notification on Backup Failure

```yaml
alias: "Alert: Backup Failure"
description: "Alerts if the latest system backup failed"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_backup_status
    to: "off"
action:
  - action: notify.notify
    data:
      title: "🚨 Home Assistant Backup Alert"
      message: "The latest system backup failed or was not found."
```

---

### Example 3: Dashboard Markdown Card

Display a dynamic system status overview directly on your dashboard:

```yaml
type: markdown
title: 🛡️ System Health Overview
content: >
  {% if is_state('binary_sensor.monitoring_global_status', 'off') %}
    ✅ **System Healthy** — No critical issues detected.
  {% else %}
    ⚠️ **Anomalies Detected!**
  {% endif %}

  ---

  {% if states('sensor.monitoring_addons') | int > 0 %}
  **Failed Add-ons:**
  {% for item in state_attr('sensor.monitoring_addons', 'list') %}
    - {{ item.name if item is mapping else item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_integrations') | int > 0 %}
  **Failed Integrations:**
  {% for item in state_attr('sensor.monitoring_integrations', 'list') %}
    - {{ item.name if item is mapping else item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_unavailable_entities') | int > 0 %}
  **Unavailable Entities ({{ states('sensor.monitoring_unavailable_entities') }}):**
  {% for item in state_attr('sensor.monitoring_unavailable_entities', 'list')[:5] %}
    - {{ item.name if item is mapping else item }}
  {% endfor %}
  {% if state_attr('sensor.monitoring_unavailable_entities', 'list') | count > 5 %}
    *...and {{ state_attr('sensor.monitoring_unavailable_entities', 'list') | count - 5 }} more.*
  {% endif %}
  {% endif %}

  ---
  💾 **Last Backup:** {{ state_attr('binary_sensor.monitoring_backup_status', 'date_last_run') }} ({{ state_attr('binary_sensor.monitoring_backup_status', 'size') }})
```

---

## 🛠️ Troubleshooting

- **Logs:** Go to **Settings → System → Logs** to inspect detailed component logs.
- **Diagnostics & Privacy:** Export diagnostic files securely when submitting an issue on GitHub; tokens, API keys, and private system details are automatically redacted.
