"""Einkaufsliste des Kontos als Home-Assistant-Aufgabenliste (``todo``).

Zwei Quellen in einer Liste: Rezept-Zutaten (verschachtelt unter
``shoppingListRecipes[].recipe.ingredients[]``) und freie Einträge
(``shoppingListCustomItems[]``). Die Aufbereitung steckt HA-frei in
``mcbridge/account.py``; hier wird nur in ``TodoItem`` gewickelt.

Vorerst **nur lesend**: Einträge werden angezeigt, inklusive abgehakt/offen.
Das Abhaken im HA (Rückschreiben per ``ShoppingListTick``) kommt erst, wenn der
Schreib-Endpunkt am echten Konto bestätigt ist – wir raten keine Schreibbefehle.
"""
from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_ACCOUNT, DOMAIN
from .coordinator import McAccountCoordinator
from .entity import main_device_id
from .mcbridge.account import shopping_entries


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]
    add([McShoppingList(daten[DATA_ACCOUNT], entry.entry_id, main_device_id(daten["coordinator"]))])


class McShoppingList(CoordinatorEntity[McAccountCoordinator], TodoListEntity):
    """Die Einkaufsliste als eine HA-Aufgabenliste (read-only)."""

    _attr_has_entity_name = True
    _attr_translation_key = "shopping_list"
    _attr_icon = "mdi:cart"

    def __init__(self, coordinator: McAccountCoordinator, entry_id: str,
                 device_id: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_shopping_list"
        if device_id:
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def todo_items(self) -> list[TodoItem] | None:
        if not self.coordinator.last_update_success:
            return None
        shopping = (self.coordinator.data or {}).get("shopping")
        return [
            TodoItem(
                summary=e.summary,
                uid=e.uid,
                status=TodoItemStatus.COMPLETED if e.ticked else TodoItemStatus.NEEDS_ACTION,
            )
            for e in shopping_entries(shopping)
        ]
