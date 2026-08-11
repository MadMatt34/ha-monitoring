## 5. Support de la Santé du Système (`system_health.py`)

Home Assistant possède un écran **Santé du système** dans **Paramètres $\rightarrow$ Système $\rightarrow$ Santé du système**. Tu peux y afficher le statut de `HA Monitoring`.

### 🛠️ L'amélioration

Créer un fichier `system_health.py` :

```python
"""Support de System Health pour HA Monitoring."""

from __future__ import annotations

from typing import Any
from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(hass: HomeAssistant, register: SystemHealthRegistration) -> None:
    """Enregistre les informations de santé de l'intégration."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Retourne les métriques clés de l'intégration."""
    coordinator_count = len(hass.data.get(DOMAIN, {}))
    return {
        "coordinators_actifs": coordinator_count,
        "api_backup_accessible": "backup" in hass.data,
    }
```
