# WIP

## TODO

- dans le code commentaires et logger en anglais
- event pour notifier d'une nouvelle erreur + options (pour quels monitoring, et activé ou non pour compteur moins)
- capteur global plus graduel (ex. 0 à 5 suivant criticité des monitorings et/ou un seuil)
- gestion d'erreur granulaire dans les étapes des scans (une erreur ne doit pas tout bloquer)\
le faire proprement nécessite de décider comment représenter l'indisponibilité individuelle de chaque sous-collecte dans HAMonitoringData. Ce serait une évolution du contrat des plateformes, pas une simple correction.
- déclenchement des scans suite abonnement aux events HA quand ça existe
- publication hacs
- implémenter les tests unitaires

## INFO

- debug : custom_components.ha_monitoring: debug

### PROMPT AUDIT

Faire un audit approfondi pour le dépot https://github.com/MadMatt34/ha-monitoring. Individuellement et globalement : vérifier la structure, la cohérence, la qualité, le typage strict ; s'assurer de l'optimisation, de l'utilisation des API natives HA, de ne pas avoir de mécanisme empirique.

A noter, pour offline_devices on s'appuie sur des entités ayant un suffixe last_seen ou la version localisée ; donc il est inutile de remettre en question ce mécanisme.
Attention, il est important de conserver le délai d'attente au démarrage de HA, et de conserver les fréquences de scan différentes pour backup, system_info, et tous les autres capteurs.
Conserver un nommage des ID des entités défini de façon statique. Le cache de DeviceInfo n'a pas besoin d'être dynamique. On verra plus tard pour implémenter les tests unitaires.
On ne tient compte que d'une base de données sous SQLLite. Le cache backup est conservé lors d'un refresh forcé ou reload de l'intégration.
