"""Gemeinsame Basis für Entitäten."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import McCoordinator


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
