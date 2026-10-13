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
            entities += [McLivePreheat(live, dev_id), McLiveScale(live, dev_id)]
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


class McLivePreheat(McLiveEntity, BinarySensorEntity):
    """Heizt auf die Zieltemperatur (``extraInfo.isPreHeat``).

    Der Wechsel von „an" auf „aus" **ist** das Signal „Zieltemperatur
    erreicht" – erst danach läuft der Schritt-Timer an. Es gibt nur im
    Rezeptbetrieb eine Vorheizphase; beim manuellen Kochen bleibt der Wert aus.

    Hinweis: Bei Schritten mit einem Ziel oberhalb des Siedepunkts (etwa
    Dampfgaren mit 120 °C) bleibt er dauerhaft an – der Fühler im Topf sieht
    nie mehr als 100 °C. Das ist richtig so und kein Fehler.
    """

    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "preheat")

    @property
    def is_on(self) -> bool | None:
        return None if self.status is None else self.status.is_preheat


class McLiveScale(McLiveEntity, BinarySensorEntity):
    """Waagen-Modus aktiv (``extraInfo.cookMode == 17``).

    Das Gewicht selbst überträgt der Dienst nicht – nur, dass gewogen wird.
    """

    _attr_icon = "mdi:scale"

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "scale")

    @property
    def is_on(self) -> bool | None:
        if (st := self.status) is None:
            return None
        return bool(st.scale_active) or st.cook_mode == "waage"
