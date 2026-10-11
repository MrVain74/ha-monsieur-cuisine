"""Sensor: Anzahl eigener Rezepte im Konto."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    add([McOwnRecipes(coordinator, entry.entry_id)])


class McOwnRecipes(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "own_recipes"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chef-hat"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_own_recipes"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("own_recipes", 0)
