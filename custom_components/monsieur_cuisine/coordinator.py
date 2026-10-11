"""Regelmäßiger Abruf von Gerät und Rezeptanzahl."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .mcbridge.client import McApiError, McAuthError, McClient

_LOGGER = logging.getLogger(__name__)


class McCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: McClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL, config_entry=entry)
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            devices = await self.client.get_devices()
            recipes = await self.client.list_own_recipes(size=1)
        except McAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except McApiError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "devices": {d.get("id"): d for d in devices},
            "own_recipes": recipes.get("total", 0),
        }
