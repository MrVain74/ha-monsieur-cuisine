"""Gemeinsame Basis für Entitäten."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LIVE_MODEL
from .coordinator import McCoordinator, McLiveCoordinator
from .mcbridge.status import DeviceLiveStatus


def main_device_id(coordinator: McCoordinator) -> str | None:
    """Das (einzige) Gerät fürs Gruppieren konto-weiter Entitäten.

    Bevorzugt ein MC3.0; sonst das erste Gerät; ``None`` wenn keins da ist
    (dann bleiben die Entitäten ohne Gerät statt falsch zugeordnet).
    """
    geraete = (coordinator.data or {}).get("devices") or {}
    for dev_id, dev in geraete.items():
        if LIVE_MODEL in (dev.get("modelName") or ""):
            return dev_id
    return next(iter(geraete), None)


class McDeviceEntity(CoordinatorEntity[McCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: McCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        dev = coordinator.data["devices"].get(device_id, {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Lidl / SilverCrest",
            model={"MC3.0": "Monsieur Cuisine Smart"}.get(dev.get("modelName"), dev.get("modelName")),
            name="Monsieur Cuisine",
        )

    @property
    def device(self) -> dict:
        return self.coordinator.data["devices"].get(self._device_id, {})


class McLiveEntity(CoordinatorEntity[McLiveCoordinator]):
    """Basis für Live-Entitäten (Push-Coordinator).

    Hängt sich über dieselben ``identifiers`` an das Gerät, das
    :class:`McDeviceEntity` angelegt hat – die Live-Werte erscheinen also am
    bekannten Gerät und nicht an einem zweiten.

    ``available`` deckt nur den Verbindungsfall ab: Solange überhaupt ein
    aktueller Live-Status vorliegt, gilt die Entität als verfügbar. Fehlt ein
    einzelner Wert (etwa die Ist-Temperatur, wenn nicht geheizt wird), liefert
    die Entität ``None`` – also „unbekannt" statt „nicht verfügbar".
    """

    _attr_has_entity_name = True

    def __init__(self, live: McLiveCoordinator, device_id: str, key: str) -> None:
        super().__init__(live)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def status(self) -> DeviceLiveStatus | None:
        return self.coordinator.data

    @property
    def available(self) -> bool:
        # Das Gerät schaltet sich nach dem Kochen selbst ab; dann kommt nichts
        # mehr und der letzte Wert wäre irgendwann irreführend.
        return self.coordinator.data is not None and not self.coordinator.stale
