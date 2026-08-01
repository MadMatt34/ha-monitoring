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
