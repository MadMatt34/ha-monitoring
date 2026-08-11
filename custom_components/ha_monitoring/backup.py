"""Support natif des hooks de sauvegarde pour HA Monitoring."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Invoqué automatiquement par HA Core juste avant le démarrage d'une sauvegarde."""
    _LOGGER.debug("[HA Monitoring] Notification de début de sauvegarde reçue de HA Core.")


async def async_post_backup(hass: HomeAssistant) -> None:
    """Appelé par HA à la fin d'une sauvegarde; aucun traitement ici.

    Le résultat final est observé via BackupManager dans le coordinator afin de
    couvrir les sauvegardes manuelles et celles lancées par d'autres intégrations.
    """
    _LOGGER.debug("[HA Monitoring] Hook post-backup reçu; résultat observé via BackupManager.")
