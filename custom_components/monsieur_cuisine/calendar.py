"""Wochenplaner des Kontos als Home-Assistant-Kalender (``calendar``).

Der Planer kennt nur Tagesfächer (``plannedTime`` = ``"YYYY-MM-DD HH:MM:SS"``,
Uhrzeit stets 00:00:00). Darum **Ganztagstermine** (``date``, nicht
``datetime``) – sonst verschiebt die Zeitzonen-Umrechnung den Eintrag auf den
Vortag. Die Aufbereitung steckt HA-frei in ``mcbridge/account.py``.

Der Coordinator hält ein Vorschaufenster (ab heute, ~1 Monat) für den Zustand
der Entität. Für beliebige Zeiträume (Kalender-Ansicht) fragt
``async_get_events`` selbst nach – in ≤1-Monats-Scheiben, weil die API je Abruf
höchstens eine Monatsspanne erlaubt.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_ACCOUNT, DOMAIN
from .coordinator import McAccountCoordinator
from .mcbridge.account import PlannerEvent, planner_events
from .mcbridge.client import McApiError, McClient

# Höchste von der API erlaubte Abrufspanne.
MAX_SPAN = timedelta(days=30)


def _als_event(ev: PlannerEvent) -> CalendarEvent:
    return CalendarEvent(
        start=ev.day,
        end=ev.day + timedelta(days=1),  # Ganztag: Ende ist exklusiv
        summary=ev.title,
        description=ev.description,
        uid=ev.uid,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]
    add([McWeeklyPlanner(daten[DATA_ACCOUNT], daten["client"], entry.entry_id)])


class McWeeklyPlanner(CoordinatorEntity[McAccountCoordinator], CalendarEntity):
    """Der Wochenplaner als Ganztags-Kalender."""

    _attr_has_entity_name = True
    _attr_translation_key = "weekly_planner"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: McAccountCoordinator, client: McClient, entry_id: str) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry_id}_weekly_planner"

    @property
    def event(self) -> CalendarEvent | None:
        """Der nächste anstehende Termin (heute oder später)."""
        heute = dt_util.now().date()
        kommende = sorted(
            (ev for ev in planner_events((self.coordinator.data or {}).get("planner"))
             if ev.day >= heute),
            key=lambda e: e.day,
        )
        return _als_event(kommende[0]) if kommende else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Termine im angefragten Zeitraum, in ≤1-Monats-Scheiben geholt."""
        gefunden: dict[str, PlannerEvent] = {}
        start = start_date
        while start < end_date:
            ende = min(start + MAX_SPAN, end_date)
            try:
                data = await self._client.get_weekly_planner(int(start.timestamp()), int(ende.timestamp()))
            except McApiError:
                break
            for ev in planner_events((data or {}).get("weeklyPlanner")):
                gefunden[ev.uid] = ev
            start = ende

        s, e = start_date.date(), end_date.date()
        # Ganztag: Termin überlappt das Fenster, wenn sein Tag im Bereich [s, e) liegt.
        return [_als_event(ev) for ev in gefunden.values() if s <= ev.day < e]
