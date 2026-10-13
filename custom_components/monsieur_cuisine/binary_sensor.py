"""Verbindungsstatus des Geräts zur Cloud (Diagnose)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_LIVE, DOMAIN, LIVE_MODEL
from .entity import McDeviceEntity, McLiveEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]
    coordinator = daten["coordinator"]
    live = daten[DATA_LIVE]

    entities: list[BinarySensorEntity] = [
        McCloudConnection(coordinator, dev_id) for dev_id in coordinator.data["devices"]
    ]
    for dev_id, dev in coordinator.data["devices"].items():
        if LIVE_MODEL in (dev.get("modelName") or ""):
            entities.append(McLiveLid(live, dev_id))
    add(entities)


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


class McLiveLid(McLiveEntity, BinarySensorEntity):
    """Deckel offen oder geschlossen.

    Hinweis: Dieses Feld liefert bisher nur der TLV-Rahmen (Tag 0x0209); in
    ``extraInfo`` kommt es nicht vor. Beim MC3.0 bleibt der Wert daher
    vorerst unbekannt, bis der Offset im Live-Rahmen gefunden ist.
    """

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "lid")

    @property
    def is_on(self) -> bool | None:
        if (st := self.status) is None or st.lid_closed is None:
            return None
        return not st.lid_closed       # "offen" = an
