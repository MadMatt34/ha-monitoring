
TODO
- tout texte dans translations
- capteur batteries faibles seuil 15% modifiable
- capteur notifs persistantes
- service pour ajouter/supprimer des exclusions (?)

- debug :
logger:
  default: info
  logs:
    custom_components.ha_monitoring: debug

TOTEST
- tout suppr et réinstall
- backup en erreur
- last_seen localisé en offline
- changement des options individuellement
  - updates : ok
  - integrations : ok
  - unavailable : ok
  - offline : ok
  - repairs
  - applications
  - automations
  - scripts
- Qualité des attributs
  - integrations : ok
  - updates : ok
  - offline : ok
  - unavailable : ok
  - backup : ok
  - repairs : 
  - applications
  - automations
  - scripts

TOCORRECT
- pour repairs_pending, nom plus convivial (translation system)
- rien remonté sur script/automation
- pour les scripts et automations en erreur, dans la liste en attribut indiquer le nom du script/automation et la date/heure de survenue de l'erreur à l'exécution

DONE
- regrouper toutes les entités dans la même application, comme le bouton
- nommer l'application Home assistant, identifier son numéro de version
- utiliser le lien externe et pas interne pour le device
- traduction interval_scan_trace dans options
- dans les options, il manque l'intervalle de scan des traces des automations et scripts
- le nom n'est pas correct dans l'attribut integrations_en_erreur de l'entité monitoring_integrations ; il faut mettre le nom de l'intégration et pas le nom du hub ajouté ou de l'application ajoutée
- dans l'attribut liste de l'entité device_offline, il faut utiliser le nom de l'appareil associé à l'entitée identifiée et pas le nom de l'entitée elle-même
- dans l'attribut liste de l'entité device_offline, ajouter la date au format ISO l'entitée last_seen associée et l'intégration correspondant au device
- erreur ouvrir options
- dans l'attribut liste de l'entité device_offline, la date au format ISO ne tient pas compte du fuseau horaire
- dans l'attribut liste de l'entité unavailable_entities, ajouter le domaine de l'entité correspondant
- dans l'attribut liste de l'entité updates, ajouter les informations de versions (version actuelle vers nouvelle version)
- j'ai modifié le CONF_STARTUP_DELAY à 60 secondes depuis les options. Pour autant j'ai mesuré qu'il met 120 secondes (deux fois plus) avant de renseigner les entités
- initialiser backup_status au démarrage de l'integ sans tenir compte tempo
- infos backup non incomplètes (date next planif, reason failed)
- click bouton pour forcer rafraichissement, ne pas remettre tout à zéro et ne pas tenir compte de la tempo de démarrage
- reload de l'intég, ne pas remettre tout à zéro et ne pas tenir compte de la tempo de démarrage
- Organiser la page options
- Exceptions pour entités indispos > revenir à un sélecteur classique entités et ajouter un sélecteur domaine
- Standardiser les noms d'attributs
- Nombre de zombies incorrect au démarrage/reload > compte ses propres capteurs tant qu'ils ne sont pas peuplés
- pour repairs_pending, la liste en attribut doit indiquer la date/heure de l'alerte, la plateforme, une dénomination plus conviviale
- pour unavailable entities, prendre aussi unknown
- pour integrations, ajouter la raison de l'échec
