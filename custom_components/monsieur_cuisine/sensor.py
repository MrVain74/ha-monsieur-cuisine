"""Sensoren: Rezeptanzahl (Abruf) und Live-Werte beim Kochen (Push)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_LIVE, DOMAIN, LIVE_MODEL
from .entity import McLiveEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]
    coordinator = daten["coordinator"]
    live = daten[DATA_LIVE]

    entities: list[SensorEntity] = [McOwnRecipes(coordinator, entry.entry_id)]

    # Live-Werte nur für Geräte, deren Rahmen wir deuten können.
    for dev_id, dev in coordinator.data["devices"].items():
        if LIVE_MODEL not in (dev.get("modelName") or ""):
            continue
        entities += [
            McLiveCookState(live, dev_id),
            McLiveCurrentTemperature(live, dev_id),
            McLiveTargetTemperature(live, dev_id),
            McLiveSpeed(live, dev_id),
            McLiveRemaining(live, dev_id),
            McLiveErrorCode(live, dev_id),
        ]
    add(entities)


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


class McLiveCookState(McLiveEntity, SensorEntity):
    """Was das Gerät gerade tut (aus ``commandType``)."""

    _attr_icon = "mdi:pot-steam"

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "cook_state")

    @property
    def native_value(self) -> str | None:
        if (st := self.status) is None:
            return None
        return st.command_type or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (st := self.status) is None:
            return {}
        # Nur Gesetztes zeigen – sonst stehen überall None herum.
        werte = {
            "betriebsart": st.cook_mode,
            "vorheizen": st.is_preheat or None,
            "drehrichtung": st.direction,
            "waage": st.scale_active or None,
            "turbo": st.turbo_active or None,
            "rezept_id": st.recipe_id,
            "schritt": st.step_index,
            "schritte_gesamt": st.total_step_index,
            # Diagnose: woher die Werte kommen und was dabei auffiel.
            "quellen": ", ".join(st.sources) or None,
            "hinweise": ", ".join(st.problems) or None,
        }
        return {k: v for k, v in werte.items() if v is not None}


class McLiveCurrentTemperature(McLiveEntity, SensorEntity):
    """Ist-Temperatur im Topf (NTC-Fühler)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "current_temperature")

    @property
    def native_value(self) -> int | None:
        return None if self.status is None else self.status.current_temp


class McLiveTargetTemperature(McLiveEntity, SensorEntity):
    """Eingestellte Ziel-Temperatur (None = Heizung aus)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "target_temperature")

    @property
    def native_value(self) -> int | None:
        return None if self.status is None else self.status.target_temp


class McLiveSpeed(McLiveEntity, SensorEntity):
    """Rührstufe. Halbstufen sind möglich, daher Dezimalwert."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"
    _attr_suggested_display_precision = 1

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "speed")

    @property
    def native_value(self) -> float | None:
        return None if self.status is None else self.status.speed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (st := self.status) is None or st.speed_raw is None:
            return {}
        # Rohwert mitgeben: ob /2 richtig ist, lässt sich so im Betrieb prüfen.
        return {"rohwert": st.speed_raw}


class McLiveRemaining(McLiveEntity, SensorEntity):
    """Restzeit beim Countdown, verstrichene Zeit bei der Stoppuhr."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "remaining_time")

    @property
    def native_value(self) -> int | None:
        if (st := self.status) is None:
            return None
        if st.is_countdown is False:
            return st.elapsed_seconds
        return st.remaining_seconds

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (st := self.status) is None:
            return {}
        werte = {
            "zeitmodus": None if st.is_countdown is None
            else ("countdown" if st.is_countdown else "stoppuhr"),
            "gesamtzeit": st.total_seconds,
            "verstrichen": st.elapsed_seconds,
            "restzeit": st.remaining_seconds,
        }
        return {k: v for k, v in werte.items() if v is not None}


class McLiveErrorCode(McLiveEntity, SensorEntity):
    """Fehlercode des Geräts (0 = kein Fehler)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, live, device_id: str) -> None:
        super().__init__(live, device_id, "error_code")

    @property
    def native_value(self) -> int | None:
        return None if self.status is None else self.status.error_code
