
TODO
Standardiser les noms d'attributs
tout texte dans translations
readme à faire
version EN (strings, translations, readme)

TOTEST
- backup en erreur
- refresh manuel après une modif
- reload après une modif
- changement des options individuellement
  - update: ok

TOCORRECT
Nombre de zombies incorrect au démarrage/reload ???
last_seen + localized
- Exceptions pour entités indispos > revenir à un sélecteur classique entités et ajouter un sélecteur domaine
Organiser la page options

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
