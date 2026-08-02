# HA Monitoring - Custom Component pour Home Assistant

**HA Monitoring** est une intégration sur mesure pour Home Assistant conçue pour surveiller la santé globale de votre système. Elle centralise les alertes, les erreurs dans les automatisations/scripts, les entités indisponibles, les appareils hors ligne, les mises à jour en attente et l'état des sauvegardes.

Toutes les entités créées par cette intégration sont automatiquement regroupées sous un **appareil unique nommé "Home Assistant"** pour une organisation optimale.

---

## 🚀 Fonctionnalités principales

- **Appareil centralisé ("Home Assistant") :** Toutes les entités (capteurs, boutons, binaires) sont regroupées sous une seule fiche d'appareil qui affiche dynamiquement la version actuelle de HA Core ainsi qu'un lien direct vers votre instance.
- **Surveillance globale :**
  - **Applications (Addons) & Intégrations :** Détection des composants en erreur.
  - **Traces d'Automatisations et de Scripts :** Détection des erreurs d'exécution récentes.
  - **Entités & Appareils :** Suivi des entités indisponibles (`unavailable`) et des appareils hors ligne (`offline`).
  - **Mises à jour & Réparations :** Suivi des mises à jour système et des alertes de réparation (Repairs).
  - **Sauvegardes (Backups) :** Vérification de l'état de la dernière sauvegarde et attributs de suivi.
- **Temporisation au démarrage :** Évite les fausses alertes pendant le chargement initial de Home Assistant.
- **Bouton d'action :** Permet de forcer un rafraîchissement immédiat de toutes les métriques.
- **Personnalisation fine via l'interface graphique :** Définition des fréquences de scan et sélection d'éléments à exclure de la surveillance.

---

## 🛠️ Configuration et Options

L'intégration se configure entièrement via l'interface graphique (**Réglages** > **Appareils et services** > **HA Monitoring**).

### Paramètres de fréquence et délais
- **Intervalle de scan général (secondes) :** Fréquence de mise à jour des capteurs (défaut : 60s).
- **Intervalle de scan des traces (minutes) :** Fréquence d'analyse des erreurs dans les traces d'automatisations et de scripts (défaut : 15 min, réglable de 1 min à 24h).
- **Délai d'inactivité hors-ligne (heures) :** Seuil à partir duquel un appareil sans activité est considéré hors ligne.
- **Temporisation au démarrage (secondes) :** Délai d'attente après le lancement de HA avant d'activer les remontées d'erreurs.

### Exclusions configurables
Vous pouvez ignorer certains éléments spécifiques pour éviter le bruit dans vos alertes :
- Addons, Intégrations et Réparations à ignorer.
- Entités spécifiques à exclure pour les automatisations, scripts, updates, entités indisponibles et appareils hors ligne.

---

## 📊 Entités fournies

Toutes les entités sont rattachées au Device **Home Assistant** :

### Capteurs (`sensor`)
| Entité | Nom | Description / Attributs |
| :--- | :--- | :--- |
| `sensor.monitoring_addons` | Monitoring Applications | Nombre d'addons en erreur (liste dans les attributs). |
| `sensor.monitoring_integrations` | Monitoring Intégrations | Nombre d'intégrations en échec. |
| `sensor.monitoring_automations` | Monitoring Automatisations | Nombre d'automatisations ayant levé une erreur. |
| `sensor.monitoring_scripts` | Monitoring Scripts | Nombre de scripts ayant levé une erreur. |
| `sensor.monitoring_updates` | Monitoring Mises à jour | Nombre de mises à jour en attente. |
| `sensor.monitoring_repairs` | Monitoring Réparations | Nombre de problèmes de réparation en attente. |
| `sensor.monitoring_unavailable_entities` | Monitoring Entités indisponibles | Nombre et liste des entités actuellement indisponibles. |
| `sensor.monitoring_offline_devices` | Monitoring Appareils hors ligne | Nombre et liste des appareils inactifs. |

### Capteurs binaires (`binary_sensor`)
| Entité | Device Class | Description |
| :--- | :--- | :--- |
| `binary_sensor.ha_monitoring_status` | `problem` | Passera à `ON` si au moins un problème (addon, intégration, automation ou script) est détecté. |
| `binary_sensor.ha_monitoring_backup` | - | Indique si la dernière sauvegarde s'est déroulée avec succès. Fournit les dates et la taille de la sauvegarde en attributs. |

### Bouton (`button`)
| Entité | Action |
| :--- | :--- |
| `button.ha_monitoring_force_scan` | Déclenche un scan immédiat du Coordinator pour rafraîchir toutes les données sans attendre l'intervalle. |

---

## 📁 Structure du projet

```text
custom_components/ha_monitoring/
├── __init__.py           # Initialisation de l'intégration et gestion du rechargement des options
├── binary_sensor.py      # Capteurs binaires (statut global, sauvegarde)
├── button.py             # Bouton pour forcer le rafraîchissement
├── config_flow.py        # Formulaires de configuration initiale et du menu d'options
├── const.py               # Constantes, icônes, clés de configuration et valeurs par défaut
├── coordinator.py        # DataUpdateCoordinator central gérant le scan et la collecte de données
├── entity.py             # Classe de base HAMonitoringBaseEntity rattachant l'ensemble au Device "Home Assistant"
├── manifest.json         # Métadonnées de l'intégration
├── sensor.py             # Capteurs de surveillance
└── translations/         # Fichiers de traduction
    ├── en.json
    └── fr.json
```

---

## 📥 Installation

1. Copiez le dossier `ha_monitoring` dans votre répertoire `custom_components/` (ex: `/config/custom_components/ha_monitoring/`).
2. Redémarrez Home Assistant.
3. Allez dans **Paramètres** > **Appareils et services** > **Ajouter une intégration**.
4. Cherchez **HA Monitoring** et validez.
---
---
---
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
- ⚡ **Rafraîchissement manuel** : Un bouton dédié permet de forcer instantanément la relance de toutes les vérifications.

---

## 📁 Structure des fichiers

```text
custom_components/ha_monitoring/
├── __init__.py          # Initialisation du composant et chargement du Coordinator
├── coordinator.py       # Logique centralisée d'analyse et temporisation
├── sensor.py            # Capteurs de comptage (add-ons, entités, etc.)
├── binary_sensor.py     # Capteurs binaires (statut global & sauvegardes)
├── button.py            # Bouton pour forcer le rafraîchissement des données
├── config_flow.py       # Flux de configuration UI et d'options
├── const.py             # Constantes, icônes et clés de configuration
├── manifest.json        # Métadonnées de l'intégration
└── translations/
    ├── fr.json          # Traductions françaises de l'UI et des entités
    └── en.json          # Traductions anglaises de l'UI et des entités (Requis pour HACS)
```

---

## 📦 Installation

### Via HACS (Recommandé)

1. Ouvrez **HACS** > **Intégrations**.
2. Cliquez sur les 3 points en haut à droite > **Dépôts personnalisés**.
3. Ajoutez l'URL de ce dépôt GitHub, choisissez la catégorie **Intégration** et validez.
4. Cliquez sur **Télécharger**, puis redémarrez Home Assistant.

### Installation manuelle

1. Téléchargez la dernière *Release* de ce dépôt.
2. Copiez le dossier `ha_monitoring` dans le répertoire `custom_components` de votre instance Home Assistant :
   ```text
   /config/custom_components/ha_monitoring/
   ```
3. Redémarrez Home Assistant.

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

### Boutons (`button.*`)

| Identifiant d'entité | Nom par défaut | Description |
| :--- | :--- | :--- |
| `button.monitoring_force_scan` | Forcer le rafraîchissement | Permet de déclencher manuellement et instantanément un scan complet du système |

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
---
---
---

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
