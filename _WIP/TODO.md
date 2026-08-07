
TODO
- tout texte d'interface dans translations
- dans le code commentaires et logger en anglais
- capteur batteries faibles seuil 15% modifiable
- service pour ajouter/supprimer des exclusions (?)
- event pour notifier d'une nouvelle erreur
- capteur global plus graduel (ex. 0 à 5 suivant criticité des monitorings et/ou un seuil)
- publication hacs
- README
  - condition avec in_startup_delay pour éviter de lancer des scripts/automations ou pour la cohérence de l'affichage lovelace
  - automations et scripts : préciser qu'on ne remonte pas si c'est antérieur à un reboot
  - applications : uniquement si démarrage auto + watchdog
  - informer des différents timings de synchro
  - exclusion entities offline par globs / wildcard patterns sur id et displayname
  - informations systems en attributs du statut global
    (comptage intégrations configurées via UI, impossible pour celles conf en yaml)
    (comptage appareils n'inclus pas les désactivés)
    (comptage devices n'inclus pas les désactivés ni scripts/automations)

TOTEST
- tout suppr et réinstall
- actualisation après backup
- backup en erreur
- last_seen localisé en offline
- changement des options individuellement
  - updates : ok
  - integrations : uniquement plateforme, ajouter possibilité nom convivial et mot clé
  - unavailable : ok > pas avec un mot clé du nom dans globs
  - offline : ok
  - repairs : uniquement plateforme, ajouter possibilité mot clé de l'issue
  - applications :
  - automations : ok
  - scripts : ok
- Qualité des attributs >> traductions ?
  - integrations : ok
  - updates : ok
  - offline : ok
  - unavailable : ok
  - backup : ok
  - repairs : ok
  - applications :
  - automations : ok
  - scripts : ok

TOCORRECT
- pour repairs_pending, nom plus convivial (translation system)
- pour les scripts et automations, translation raison de l'erreur
- pour integrations : prendre le nom affiché dans l'UI, reason est à traduire

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
- pour les scripts et automations en erreur, dans la liste en attribut indiquer le nom du script/automation et la date/heure de survenue de l'erreur à l'exécution
- liste d'exclusion entités par globs
- capteur système (version, uptime host, uptime HA, métrics contenus, taille DB)


INFO
- debug : custom_components.ha_monitoring: debug
- system ligne 256 : pour exclure basé sur 1 morceau : if any(ex in issue_identifier for ex in excluded) etc.
- si un script/automation est en erreur et qu'il s'exécute correctement ensuite, le retirer de la liste
