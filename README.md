# HA Monitoring - Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Component-blue.svg)](https://www.home-assistant.io/)
[![Latest Release](https://img.shields.io/github/v/release/MadMatt34/ha-monitoring?color=green)](https://github.com/MadMatt34/ha-monitoring/releases)

![HA Monitoring for Home Assistant](https://github.com/MadMatt34/ha-monitoring/blob/main/logo.png)

[🇫🇷 README en FRANÇAIS 🇫🇷](https://github.com/MadMatt34/ha-monitoring/blob/main/README.fr.md)

**HA Monitoring** is a custom integration for Home Assistant designed to monitor system health and components in real time. It centralizes system information and tracks issues across add-ons, integrations, automations, scripts, unavailable entities, offline devices, pending updates, active repairs, and backup statuses.

> [!IMPORTANT]
> This integration is not intended to automatically fix errors, but rather to centralize information that is often hidden or hard to find. You can then build custom automations based on these metrics.

---

## ⚡ Main Features

- **Centralized Device ("Home Assistant"):** All entities (sensors, buttons, binary sensors) are grouped under a single device card displaying the current HA Core version along with a direct link to your instance.
- **System Information:** Reports versions and boot timestamps for HAOS and HA, total counts of various elements, database size, and recorder settings.
- **Global Monitoring:**
  - **Updates & Repairs:** Real-time tracking of system updates and pending repair issues.
  - **Backups:** Verification of the latest backup status and associated tracking attributes.
  - **Add-ons & Integrations:** Detection of failed or errored components.
  - **Automation & Script Traces:** Detection of recent execution errors.
  - **Entities & Devices:** Tracking of `unavailable` entities and `offline` devices.
- **Startup Grace Period:** Prevents false alarms during Home Assistant's initial boot sequence.
- **Action Button:** Trigger an immediate full system refresh on demand.
- **Fine-grained Customization via UI:** Adjust scan frequencies and granularly exclude specific items from being monitored.

---

## 🧩 Installation

### Option 1: Installation via HACS (Custom Repository - 📌 Recommended)

1. Open **HACS**.
2. Click the 3 dots in the top right corner > **Custom repositories**.
3. Add: `https://github.com/MadMatt34/ha-monitoring`
4. Select category **Integration** and click **Add**.
5. Click **Download**, then restart Home Assistant.

### Option 2: Manual Installation

1. Download the latest *Release* from this repository.
2. Copy the `ha_monitoring` folder into your `/config/custom_components/` directory.
3. Restart Home Assistant to detect the new integration.

---

## 🚀 Integration Setup

Configuration is **100% UI-based** within Home Assistant.

1. Go to **Settings** > **Devices & Services**.

   [![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)](https://my.home-assistant.io/redirect/integrations/)
2. Click **Add Integration** (bottom right).
3. Search for **HA Monitoring** and select it.
4. Enter your initial settings (or leave default values) and submit.

---

## ⚙️ Modifying Settings

You can adjust thresholds and exclusion lists at any time:

1. Go to **Settings** > **Devices & Services** > **HA Monitoring**.
2. Click the **CONFIGURE** button *(gear icon)*.
3. Adjust the desired parameters:
    - **Startup Grace Period** (in seconds): Waiting time upon boot before enabling scans (default: 2 min).
    - **Refresh Interval** (in seconds): Main data refresh frequency (default: 3 min).
    - **System Info Scan Interval** (in hours): Refresh frequency for general system stats (default: 24 hours).
    - **Traces Scan Interval** (in minutes): Frequency for scanning automation and script execution trace errors (default: 30 min).
    - **Offline Inactivity Threshold** (in hours): Inactivity duration before marking a device as offline (default: 24h).
    - **Exclusions**: Select add-ons, integrations, repairs, updates, automations, scripts, devices, or entities to ignore.

---

## 📡 Provided Entities

All entities are attached to the **Home Assistant** Device:

> [!TIP]
> Each entity contains a list attribute detailing the items detected.
>
> Use **Settings** > **Tools** > **States** to explore all attributes.
>
> [![Open your Home Assistant instance and show your state tools.](https://my.home-assistant.io/badges/developer_states.svg)](https://my.home-assistant.io/redirect/developer_states/)

### Sensors (`sensor.*`)

| Entity | Name | Description / Attributes |
| :--- | :--- | :--- |
| `sensor.monitoring_applications` | Monitoring Failded Applications | Number of failed applications. |
| `sensor.monitoring_integrations` | Monitoring Failded Integrations | Number of failed integrations. |
| `sensor.monitoring_automations` | Monitoring Failded Automations | Number of automations that threw an error. |
| `sensor.monitoring_scripts` | Monitoring Failded Scripts | Number of scripts that threw an error. |
| `sensor.monitoring_updates` | Monitoring Pending Updates | Number of pending updates. |
| `sensor.monitoring_repairs` | Monitoring Pending Repairs | Number of active repair issues. |
| `sensor.monitoring_unavailable_entities` | Monitoring Unavailable Entities | Count and list of currently unavailable entities. |
| `sensor.monitoring_offline_devices` | Monitoring Offline Devices | Count and list of inactive devices. |

### Binary Sensors (`binary_sensor.*`)

| Entity | Device Class | Name | Description |
| :--- | :--- | :--- | :--- |
| `binary_sensor.monitoring_global_status` | `problem` | Monitoring Global Status | Turns `ON` if at least one critical issue (add-on, integration, automation, or script) is detected. System info are provided in attributes. |
| `binary_sensor.monitoring_backup` | - | Monitoring Backup Status | Turns `OFF` if the last backup failed. Provides backup dates, sizes, and failure reasons as attributes. |

### Buttons (`button.*`)

| Entity | Name | Description |
| :--- | :--- | :--- |
| `button.monitoring_force_scan` | Monitoring Force Refresh | Manually triggers an immediate full system scan. |

---

## 💡 Additional Details

### Startup Grace Period Details

The first scan following a Home Assistant boot will wait until the configured grace period expires (default 2 min). This prevents false alerts before all integrations and sensors have finished loading.

> [!TIP]
> Use the attribute `startup_delay = False` as a condition in your scripts/automations or dashboard view visibility.

### Data Refresh Intervals Details

- **System Info Attributes:** Updated according to the frequency defined in options (default 24 hours).

- **Backup Sensor:** Updated immediately following the completion of a backup execution event.

- **All Other Sensors:** Updated according to the main scan interval defined in options (default 3 min).

> [!NOTE]
> All sensors and attributes are refreshed upon integration startup, when clicking the `Force Refresh` button, or when changing integration settings.

### Specific Sensor & Attribute Notes

* **Backup Sensor:** Only the official Backup integration is taken into account; its current implementation does not provide explicit failure messages. The backup failure state is lost after a restart.

* **Offline Devices Sensor:** The scan relies on a device entity of type `sensor`, with the `timestamp` device class, an `last_seen` or localized suffix, and whose state is an ISO-formatted date.

* **Applications Sensor:** The scan reports applications configured with both `Start on boot` and `Watchdog` enabled that are not currently started.

* **Global Status System Info Attributes:**
  - Integrations count: Counts UI-configured integrations (YAML-configured ones cannot be tracked).
  - Devices count: Disabled devices are excluded.
  - Entities count: Disabled entities, script entities, and automation entities are excluded.
  - Database Size: Only the standard installation using SQLite is supported.


---

## 🤖 Automations & Dashboard Examples

### Example 1: Notification on System Issue

```yaml
alias: "Alert: System Issue Detected"
description: "Sends a mobile notification if a component enters an error state"
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
        Issue detected on your system:
        - Errored Add-ons: {{ states('sensor.monitoring_applications') }}
        - Errored Integrations: {{ states('sensor.monitoring_integrations') }}
        - Errored Automations: {{ states('sensor.monitoring_automations') }}
        - Unavailable Entities: {{ states('sensor.monitoring_unavailable_entities') }}
mode: single
```

---

### Example 2: Notification on Backup Failure

```yaml
alias: "Alert: Backup Failure"
description: "Alerts if the latest backup failed"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_backup
    to: "off"
action:
  - action: notify.notify
    data:
      title: "🚨 Home Assistant Backup Failure"
      message: "The latest backup failed or no backup was found."
```

---

### Example 3: Dashboard Markdown Card

Display a detailed and dynamic system report directly on your dashboard:

```yaml
type: markdown
title: 🛡️ System Status
content: >
  {% if is_state('binary_sensor.monitoring_global_status', 'off') %}
    ✅ **System Stable** — No major issues detected.
  {% else %}
    ⚠️ **Anomalies Detected!**
  {% endif %}

  ---

  {% if states('sensor.monitoring_applications') | int > 0 %}
  **Errored Add-ons:**
  {% for item in state_attr('sensor.monitoring_applications', 'list') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_integrations') | int > 0 %}
  **Errored Integrations:**
  {% for item in state_attr('sensor.monitoring_integrations', 'list') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_unavailable_entities') | int > 0 %}
  **Unavailable Entities ({{ states('sensor.monitoring_unavailable_entities') }}):**
  {% for item in state_attr('sensor.monitoring_unavailable_entities', 'list')[:5] %}
    - {{ item }}
  {% endfor %}
  {% if state_attr('sensor.monitoring_unavailable_entities', 'list') | count > 5 %}
    *...and {{ state_attr('sensor.monitoring_unavailable_entities', 'list') | count - 5 }} more.*
  {% endif %}
  {% endif %}

  ---
  💾 **Last Backup:** {{ state_attr('binary_sensor.monitoring_backup', 'date_last_run') }} ({{ state_attr('binary_sensor.monitoring_backup', 'size') }})
```

---

## 🛠️ Troubleshooting

- Check your logs: **Settings → System → Logs**
- Diagnostics & Privacy: Safe diagnostic export is supported when opening an issue on GitHub. Access tokens, credentials, and personal data are automatically anonymized.

---

## *Note*

*I am not a developer; I built this integration with the help of AI. Feel free to contribute!*
