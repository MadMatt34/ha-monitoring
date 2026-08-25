# HA Monitoring - Intégration pour Home Assistant

[![Latest Release](https://img.shields.io/github/v/release/MadMatt34/ha-monitoring?color=green)](https://github.com/MadMatt34/ha-monitoring/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Component-blue.svg)](https://www.home-assistant.io/)

[![HACS Check](https://github.com/MadMatt34/ha-monitoring/actions/workflows/hacs.yml/badge.svg)](https://github.com/MadMatt34/ha-monitoring/actions/workflows/hacs.yml)
[![Hassfest Check](https://github.com/MadMatt34/ha-monitoring/actions/workflows/hassfest.yml/badge.svg)](https://github.com/MadMatt34/ha-monitoring/actions/workflows/hassfest.yml)

![HA Monitoring for Home Assistant](https://github.com/MadMatt34/ha-monitoring/blob/main/logo.png)

[🇬🇧 README in ENGLISH 🇬🇧](https://github.com/MadMatt34/ha-monitoring/blob/main/README.md)

**HA Monitoring** est une intégration personnalisée pour Home Assistant conçue pour surveiller l'état de santé du système et d'autres composants en temps réel. Elle centralise certaines informations système, et la détection des dysfonctionnements (applications, intégrations, automatisations, scripts), des entités indisponibles, des appareils hors ligne, des mises à jour et des réparations en attente, de l'état des sauvegardes.

> [!IMPORTANT]
> Cette intégration n'a pas vocation à corriger les erreurs, uniquement centraliser toutes ces informations souvent invisibles ou difficilement accessibles au premier abord. A vous de construire ensuite les automatisations qui vous conviennent.

---

## ⚡ Fonctionnalités principales

- **Appareil centralisé ("Home Assistant") :** Toutes les entités (capteurs, boutons, binaires) sont regroupées sous une seule fiche d'appareil qui affiche la version actuelle de HA Core ainsi qu'un lien direct vers votre instance.
- **Informations système :** Indique les versions et date/heure des démarrages de HAOS et de HA, les quantités des différents éléments, taille de base et paramètres du recorder.
- **Surveillance globale :**
  - **Mises à jour & Réparations :** Suivi des mises à jour et des alertes de réparation.
  - **Sauvegardes :** Vérification de l'état de la dernière sauvegarde et attributs de suivi.
  - **Applications (Addons) & Intégrations :** Détection des composants stoppés et en erreur.
  - **Traces d'Automatisations et de Scripts :** Détection des erreurs d'exécution.
  - **Entités & Appareils :** Suivi des entités indisponibles (`unavailable`) et des appareils hors ligne (`offline`).
- **Temporisation au démarrage :** Évite les fausses alertes pendant le chargement initial de Home Assistant.
- **Bouton d'action :** Permet de forcer un rafraîchissement immédiat de toutes les collectes.
- **Personnalisation fine via l'interface graphique :** Définition des fréquences de scan et sélection granulaire d'éléments à exclure de la surveillance.

---

## 🧩 Installation

### Option 1 : Installation via HACS (dépôt personnalisé - 📌 recommandée)

1. Ouvrir **HACS**  
2. Cliquer sur les 3 points en haut à droite > **Dépôts personnalisés**.
3. Ajouter : `https://github.com/MadMatt34/ha-monitoring`
4. Choisir la catégorie **Intégration** et valider
5. Cliquer sur **Télécharger**, puis redémarrer Home Assistant.

### Option 2 : Installation manuelle

1. Télécharger la dernière *Release* de ce dépôt.
2. Copier le dossier `ha_monitoring` dans `/config/custom_components/`.
3. Redémarrer Home Assistant pour faire détecter la nouvelle intégration.

---

## 🚀 Configuration de l'intégration

L'installation se fait **100 % via l'interface graphique** de Home Assistant.

1. Dans Home Assistant, aller dans **Paramètres** > **Appareils et services**.\
   [![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)](https://my.home-assistant.io/redirect/integrations/)
2. Cliquer sur **Ajouter une intégration** (en bas à droite).
3. Rechercher **HA Monitoring** et sélectionner.
4. Renseigner les paramètres initiaux (ou laisser les valeurs par défaut) et valider.

---

## ⚙️ Modification des paramètres

Vous pouvez modifier les seuils et les listes d'exclusions à tout moment :

1. Aller dans **Paramètres** > **Appareils et services** > **HA Monitoring**.
2. Cliquer sur le bouton **CONFIGURER** *(roue crantée)*.
3. Régler les paramètres souhaités :
    - **Délai de grâce au démarrage** (en secondes) : Temps d'attente au boot avant d'activer le premier scan (par défaut : 2 min).
    - **Intervalle de rafraîchissement** (en secondes) : Fréquence d'actualisation des données (par défaut : 3 min).
    - **Intervalle de scan des informations système** (en heures) : Fréquence d'actualisation des informations système (par défaut 24 heures).
    - **Intervalle de scan des traces** (en minutes) : Fréquence d'analyse des erreurs dans les traces d'automatisations et de scripts (par défaut : 30 min).
    - **Seuil d'inactivité hors ligne** (en heures) : Durée d'inactivité avant de considérer un appareil hors ligne (par défaut : 24h).
    - **Exclusions** : Sélectionnez les applications, intégrations, réparations, mises à jour, automatisations, scripts, appareils, entités à ignorer.

---

## 📡 Entités fournies

Toutes les entités sont rattachées à l'appareil **Home Assistant** :

> [!TIP]
> Chaque entité contient des attributs listant les éléments détectés.\
> Utilisez **Paramètres** > **Outils** > **Etats** pour explorer tous les attributs.

### Capteurs (`sensor.*`)

| Entité | Nom | Description / Attributs |
| :--- | :--- | :--- |
| `sensor.monitoring_applications` | Monitoring Applications stoppées | Nombre d'applications à l'arrêt. Liste en attribut. |
| `sensor.monitoring_integrations` | Monitoring Intégrations en erreur | Nombre d'intégrations en échec. Liste en attribut. |
| `sensor.monitoring_automations` | Monitoring Automatisations en erreur | Nombre d'automatisations ayant levé une erreur. Liste en attribut. |
| `sensor.monitoring_scripts` | Monitoring Scripts en erreur | Nombre de scripts ayant levé une erreur. Liste en attribut. |
| `sensor.monitoring_updates` | Monitoring Mises à jour en attente | Nombre de mises à jour en attente. Liste en attribut. |
| `sensor.monitoring_repairs` | Monitoring Réparations en attente | Nombre de réparations en attente. Liste en attribut. |
| `sensor.monitoring_unavailable_entities` | Monitoring Entités indisponibles | Nombre et liste des entités actuellement indisponibles. |
| `sensor.monitoring_offline_devices` | Monitoring Appareils hors ligne | Nombre et liste des appareils inactifs depuis le délai configuré. |

### Capteurs binaires (`binary_sensor.*`)

| Entité | Device Class | Nom | Description |
| :--- | :--- | :--- | :--- |
| `binary_sensor.monitoring_global_status` | `problem` | Monitoring Statut Global | Passe à `on` si au moins un problème critique (application, intégration, automatisation ou script) est détecté. Informations système fournies en attributs. |
| `binary_sensor.monitoring_backup` | - | Monitoring État de la sauvegarde | Passe à `off` si la dernière sauvegarde a échoué. Fournit en attributs les dates et la taille de la sauvegarde, la raison de l'éventuel échec. |

### Boutons (`button.*`)

| Entité | Nom | Description |
| :--- | :--- | :--- |
| `button.monitoring_force_scan` | Monitoring Forcer le scan | Permet de déclencher manuellement et instantanément un scan complet |

Les attributs du bouton exposent les horodatages des analyses les plus récentes

- `last_scan`: dernier scan de monitoring standard
- `last_traces_scan`: dernier scan des traces des automatisations/scripts
- `last_system_info_scan`: dernier scan des informations système
- `last_backup_scan`: dernier scan des informations de sauvegarde

---

## 💡 Précisions complémentaires

### Précisions sur la période de grâce au démarrage

Le premier scan qui suit un démarrage de Home Assistant attendra la fin de la période de grâce configurée dans les paramètres (par défaut 2 min). Cela évite d'obtenir des valeurs fausses si l'ensemble des intégrations et capteurs n'ont pas été chargés.

> [!TIP]
> Utilisez l'attribut `startup_delay = False` comme condition pour le lancement de vos scripts/automatisations ou pour l'affichage de vos tableaux de bord.

### Précisions sur les délais d'actualisation des données

- **Attributs informations système :** ces attributs du capteur `binary_sensor.monitoring_global_status` sont actualisés suivant le fréquence définie dans les paramètres (par défaut 24 heures).
- **Capteur backup :** ce capteur et ses attributs sont actualisés après l'exécution d'une sauvegarde.
- **Tous les autres capteurs :** tous les autres capteurs et leurs attributs sont actualisés suivant le fréquence définie dans les paramètres (par défaut 3 min).

> [!NOTE]
> L'ensemble des capteurs et leurs attributs sont actualisés au démarrage de l'intégration, lors de l'utilisation du bouton `Forcer le scan` ou après la modification de paramètres de l'intégration.

### Précisions sur certains capteurs et attributs

- **Capteur Sauvegarde :** Seule l'intégration `Backup` officielle est prise en compte ; son fonctionnement actuel ne permet pas d'avoir des messages d'échec explicites. L'état de sauvegarde en échec est perdu au redémarrage.
- **Capteur Appareils hors ligne :** Le scan se base sur une entité de l'appareil, de type `sensor`, de classe `timestamp` avec un suffixe `last_seen` ou localisé, et son état est une date au format ISO *(ce qui est fait par Z-Wave, Zigbee2MQTT par exemple)*.
- **Capteur Applications :** Le scan remonte les applications configurées avec les paramètres `Lancer au démarrage` et `Chien de garde` activés, et qui ne seraient pas démarrées.
- **Attributs Informations système du capteur Statut Global :**
  - Nombre d'intégrations  : comptabilise les intégrations visibles dans l'interface utilisateur, à l'exeption de celles configurées en yaml (impossible).
  - Nombre d'appareils : les appareils désactivés ne sont pas comptabilisés.
  - Nombre d'entités : les entités désactivées ne sont pas comptabilisées, et les entités pour les scripts et automatisations non plus.
  - Taille de la base de donnée : uniquement l'installation standard est considérée (SQLLite)

### Précisions sur les exclusions en texte-libre

- **Exclusion Applications :** Par nom convivial ou une partie, par nom technique ou une partie.
- **Exclusions Intégrations :** Par nom convivial ou une partie, par nom technique ou une partie, par domaine, par ID ou une partie.
- **Exclusions Réparations :** Par nom convivial ou une partie, par domaine, par ID ou une partie.
- **Exclusions Entités :** Par nom convivial ou une partie, par ID ou une partie.

> [!NOTE] ***Filtrage par partie (Globs) :***\
> - Insensible à la casse.
> - \* → n'importe quelle séquence de caractères.
> - ? → un seul caractère.
> - Une chaîne sans caractère générique est cherchée comme une correspondance exacte.

---

## 🤖 Exemples d'automatisations & Dashboard

### Exemple 1 : Notification en cas de problème système

```yaml
alias: "Alerte : Problème Système Détecté"
description: "Envoie une notification mobile si un élément tombe en erreur"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_global_status
    to: "on"
condition: []
action:
  - action: notify.notify
    data:
      title: "⚠️ HA Monitoring - Alerte Système"
      message: >
        Problème détecté sur votre système :
        - Applications en erreur : {{ states('sensor.monitoring_applications') }}
        - Intégrations : {{ states('sensor.monitoring_integrations') }}
        - Automations : {{ states('sensor.monitoring_automations') }}
        - Entités indisponibles : {{ states('sensor.monitoring_unavailable_entities') }}
mode: single
```

---

### Exemple 2 : Notification en cas d'échec de sauvegarde

```yaml
alias: "Alerte : Échec Sauvegarde"
description: "Alerte si la dernière sauvegarde a échoué"
trigger:
  - platform: state
    entity_id: binary_sensor.monitoring_backup
    to: "off"
action:
  - service: notify.notify
    data:
      title: "🚨 Échec de Sauvegarde Home Assistant"
      message: "La dernière sauvegarde a échoué ou aucune sauvegarde n'a été trouvée."
```

---

### Exemple 3 : Carte Markdown Dashboard

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

  {% if states('sensor.monitoring_applications') | int > 0 %}
  **Applications en erreur :**
  {% for item in state_attr('sensor.monitoring_applications', 'list') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_integrations') | int > 0 %}
  **Intégrations en erreur :**
  {% for item in state_attr('sensor.monitoring_integrations', 'list') %}
    - {{ item }}
  {% endfor %}
  {% endif %}

  {% if states('sensor.monitoring_unavailable_entities') | int > 0 %}
  **Entités indisponibles ({{ states('sensor.monitoring_unavailable_entities') }}) :**
  {% for item in state_attr('sensor.monitoring_unavailable_entities', 'list')[:5] %}
    - {{ item }}
  {% endfor %}
  {% if state_attr('sensor.monitoring_unavailable_entities', 'list') | count > 5 %}
    *...et {{ state_attr('sensor.monitoring_unavailable_entities', 'list') | count - 5 }} autre(s).*
  {% endif %}
  {% endif %}

  ---
  💾 **Dernière sauvegarde :** {{ state_attr('binary_sensor.monitoring_backup', 'date_last_run') }} ({{ state_attr('binary_sensor.monitoring_backup', 'size') }})
```

---

## 🛠️ Dépannage

- Consultez les logs : **Paramètres → Système → Journaux**
- Diagnostics & Vie privée : Exportez vos fichiers de diagnostic en toute sécurité lors de l'ouverture d'un ticket sur GitHub ; vos jetons d'accès, identifiants et données personnelles sont automatiquement anonymisés.

---

## 🌐 Langues prises en charge

🇬🇧 English • 🇫🇷 Français
