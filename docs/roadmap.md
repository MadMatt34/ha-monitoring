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
