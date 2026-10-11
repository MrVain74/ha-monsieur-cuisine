"""Verbindungsstatus des Geräts zur Cloud (Diagnose)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import McDeviceEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    add(McCloudConnection(coordinator, dev_id) for dev_id in coordinator.data["devices"])


class McCloudConnection(McDeviceEntity, BinarySensorEntity):
    """Ob das Gerät gerade mit der Hersteller-Cloud verbunden ist.

    Hinweis: Der MC schaltet sich nach kurzer Zeit selbst ab – der Wert zeigt
    eher "wurde gerade benutzt" als einen Dauerzustand.
    """

    _attr_translation_key = "cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_cloud_connection"

    @property
    def is_on(self) -> bool:
        return self.device.get("iotConnectionStatus") == "CONNECT"
