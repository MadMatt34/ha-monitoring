# 🛡️ HA Monitoring — Surveillance Système pour Home Assistant

**HA Monitoring** est une intégration personnalisée pour Home Assistant conçue pour surveiller l'état de votre système en temps réel. Elle centralise la détection des dysfonctionnements (add-ons, intégrations, automations, scripts), des entités indisponibles, des appareils hors ligne, des mises à jour, des réparations en attente et de l'état des sauvegardes.

Elle inclut une **temporisation intelligente au démarrage** pour éviter les fausses alertes au lancement de Home Assistant.

---

## 🚀 Fonctionnalités

- 🔄 **Collecte centralisée** via un `DataUpdateCoordinator` unique pour des performances optimales.
- ⏱️ **Délai de grâce au démarrage** : Masque temporairement les erreurs le temps que tous vos appareils et intégrations se connectent.
- 🚫 **Exclusions granulaires** : Excluez facilement des automations, scripts, entités ou add-ons spécifiques du suivi d'erreur.
- 📦 **Suivi des sauvegardes** : Vérification de l'état, de la date et de la taille de la dernière sauvegarde.
- 📊 **Statut Global** : Un capteur binaire unique pour déclencher des alertes globales.

---

## 📁 Structure des fichiers

```text
custom_components/ha_monitoring/
├── __init__.py          # Initialisation du composant et chargement du Coordinator
├── coordinator.py       # Logique centralisée d'analyse et temporisation
├── sensor.py             # Capteurs de comptage (add-ons, entités, etc.)
├── binary_sensor.py      # Capteurs binaires (statut global & sauvegardes)
├── config_flow.py       # Flux de configuration UI et d'options
├── const.py              # Constantes, icônes et clés de configuration
├── manifest.json         # Métadonnées de l'intégration
└── translations/
    └── fr.json          # Traductions françaises de l'UI et des entités
```

---

## 📦 Installation

### Option 1 : Installation manuelle

1. Téléchargez le dossier `ha_monitoring`.
2. Copiez le dossier dans le répertoire `custom_components` de votre instance Home Assistant :
   ```text
   /config/custom_components/ha_monitoring/
   ```
3. Redémarrez Home Assistant.

### Option 2 : Via HACS (Dépôt personnalisé)

1. Ouvrez **HACS** > **Intégrations**.
2. Cliquez sur les 3 points en haut à droite > **Dépôts personnalisés**.
3. Ajoutez l'URL de votre dépôt GitHub, choisissez la catégorie **Intégration** et validez.
4. Cliquez sur **Télécharger**, puis redémarrez Home Assistant.

---

## ⚙️ Configuration

1. Dans Home Assistant, allez dans **Réglages** > **Appareils et services**.
2. Cliquez sur **Ajouter une intégration** en bas à droite.
3. Recherchez **HA Monitoring**.
4. Renseignez les paramètres initiaux (ou laissez les valeurs par défaut) et validez.

---

## 🛠️ Modification des paramètres

Vous pouvez modifier les seuils et les listes d'exclusions à tout moment :

1. Rendez-vous dans **Réglages** > **Appareils et services** > **HA Monitoring**.
2. Cliquez sur le bouton **CONFIGURER**.
3. Réglez les options souhaitées :
   - **Intervalle de rafraîchissement** : Délai d'actualisation des données (ex: 60s).
   - **Seuil d'inactivité hors ligne** : Durée d'inactivité avant de considérer un appareil hors ligne (ex: 24h).
   - **Délai de grâce au démarrage** : Temps d'attente au boot avant d'activer les alertes (ex: 180s).
   - **Exclusions** : Sélectionnez les entités, add-ons ou intégrations à ignorer.

---

## 📊 Entités disponibles

### Capteurs (`sensor.*`)

| Identifiant d'entité | Nom par défaut | Description |
| :--- | :--- | :--- |
| `sensor.monitoring_addons` | Monitoring Applications | Nombre d'add-ons arrêtés ou en erreur |
| `sensor.monitoring_integrations` | Monitoring Intégrations | Nombre d'intégrations échouées |
| `sensor.monitoring_automations` | Monitoring Automatisations | Nombre d'automations ayant généré une erreur |
| `sensor.monitoring_scripts` | Monitoring Scripts | Nombre de scripts ayant généré une erreur |
| `sensor.monitoring_updates` | Monitoring Mises à jour | Mises à jour système / HACS en attente |
| `sensor.monitoring_repairs` | Monitoring Réparations | Corrections / Réparations système requises |
| `sensor.monitoring_unavailable_entities` | Monitoring Entités indisponibles | Nombre d'entités au statut `unavailable` |
| `sensor.monitoring_offline_devices` | Monitoring Appareils hors ligne | Nombre d'appareils muets selon le seuil configuré |

> **Note :** Chaque capteur contient un attribut de liste (ex: `addons_en_erreur`, `entites_indisponibles`) listant précisément les éléments détectés.

### Capteurs binaires (`binary_sensor.*`)

| Identifiant d'entité | Nom par défaut | Description |
| :--- | :--- | :--- |
| `binary_sensor.monitoring_global_status` | Monitoring Statut Global | Passe à `on` (Problème) si au moins une erreur critique est détectée |
| `binary_sensor.monitoring_backup_status` | Monitoring État de la sauvegarde | Passe à `off` si la dernière sauvegarde a échoué |

---

## 💡 Exemples d'automatisations & Dashboard

### 1. Automation : Notification en cas de problème système

```yaml
alias: "Alerte : Problème Système Détecté"
description: "Envoie une notification mobile si un élément tombe en erreur"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_global_status
    to: "on"
condition: []
action:
  - service: notify.notify
    data:
      title: "⚠️ HA Monitoring - Alerte Système"
      message: >
        Problème détecté sur votre système :
        - Add-ons en erreur : {{ states('sensor.monitoring_addons') }}
        - Intégrations : {{ states('sensor.monitoring_integrations') }}
        - Automations : {{ states('sensor.monitoring_automations') }}
        - Entités indisponibles : {{ states('sensor.monitoring_unavailable_entities') }}
mode: single
```

---

### 2. Automation : Notification en cas d'échec de sauvegarde

```yaml
alias: "Alerte : Échec Sauvegarde"
description: "Alerte si la dernière sauvegarde a échoué"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_backup_status
    to: "off"
action:
  - service: notify.notify
    data:
      title: "🚨 Échec de Sauvegarde Home Assistant"
      message: "La dernière sauvegarde a échoué ou aucune sauvegarde n'a été trouvée."
```

---

### 3. Carte Markdown Dashboard (Lovelace)

Affichez un rapport détaillé et dynamique directement sur votre tableau de bord :

```yaml
type: markdown
title: 🛡️ État du Système
content: >
  {% if is_state('binary_sensor.monitoring_global_status', 'off') %}
    ✅ **Système stable** — Aucun problème majeur détecté.
  {% else %}
    ⚠️ **Des anomalies ont été détectées !**
  {% endif %}

  ---

  {% if states('sensor.monitoring_addons') | int > 0 %}
  **Add-ons en erreur :**
  {% for item in state_attr('sensor.monitoring_addons', 'addons_en_erreur') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_integrations') | int > 0 %}
  **Intégrations en erreur :**
  {% for item in state_attr('sensor.monitoring_integrations', 'integrations_en_erreur') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_unavailable_entities') | int > 0 %}
  **Entités indisponibles ({{ states('sensor.monitoring_unavailable_entities') }}) :**
  {% for item in state_attr('sensor.monitoring_unavailable_entities', 'entites_indisponibles')[:5] %}
    - {{ item }}
  {% endfor %}
  {% if state_attr('sensor.monitoring_unavailable_entities', 'entites_indisponibles') | count > 5 %}
    *...et {{ state_attr('sensor.monitoring_unavailable_entities', 'entites_indisponibles') | count - 5 }} autre(s).*
  {% endif %}
  {% endif %}

  ---
  💾 **Dernière sauvegarde :** {{ state_attr('binary_sensor.monitoring_backup_status', 'date_sauvegarde') }} ({{ state_attr('binary_sensor.monitoring_backup_status', 'taille_sauvegarde') }})
```
