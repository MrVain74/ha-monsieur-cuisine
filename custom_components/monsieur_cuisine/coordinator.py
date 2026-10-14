"""Regelmäßiger Abruf von Gerät und Rezeptanzahl, plus Live-Status (Push)."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import utcnow

from .const import (
    ACCOUNT_UPDATE_INTERVAL,
    DOMAIN,
    LIVE_MODEL,
    LIVE_RETRY_MAX,
    LIVE_RETRY_START,
    LIVE_STALE_AFTER,
    LIVE_WATCHDOG,
    PLANNER_WINDOW_DAYS,
    UPDATE_INTERVAL,
)
from .mcbridge.client import McApiError, McAuthError, McClient
from .mcbridge.grpcstatus import GRPC_HOST, DeviceStatus, stream_device_status
from .mcbridge.status import DeviceLiveStatus, decode_status

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


class McAccountCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Konto-Daten: Einkaufsliste und Wochenplaner-Fenster.

    Beide ändern sich selten; ein ruhiger Abruf reicht. Der Planer wird nur für
    ein Vorschaufenster (ab heute, ~1 Monat) geholt – für beliebige Zeiträume
    fragt die Kalender-Entität selbst nach (``async_get_events``), denn die API
    erlaubt je Abruf höchstens eine Monatsspanne.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: McClient) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_account",
                         update_interval=ACCOUNT_UPDATE_INTERVAL, config_entry=entry)
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"shopping": None, "planner": []}
        try:
            data["shopping"] = await self.client.get_shopping_list()
        except McAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except McApiError as err:
            raise UpdateFailed(str(err)) from err

        start = dt_util.start_of_local_day()
        end = start + timedelta(days=PLANNER_WINDOW_DAYS)
        try:
            planer = await self.client.get_weekly_planner(int(start.timestamp()), int(end.timestamp()))
            data["planner"] = (planer or {}).get("weeklyPlanner", [])
        except McAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except McApiError as err:
            # Ein Planer-Fehler darf die Einkaufsliste nicht mitreißen.
            _LOGGER.warning("MC-Konto: Wochenplaner-Abruf fehlgeschlagen: %s", err)
        return data


class McLiveCoordinator(DataUpdateCoordinator[DeviceLiveStatus | None]):
    """Live-Status des Geräts – Push über den gRPC-Strom, kein Abrufintervall.

    ``loginDeviceStatus`` ist ein Server-Stream: der Dienst schickt bei jeder
    Zustandsänderung eine Meldung. Deshalb kein ``update_interval``, sondern
    eine Hintergrundaufgabe, die den Strom offen hält und jede Meldung per
    ``async_set_updated_data`` an die Entitäten weitergibt.

    Der Strom endet regelmäßig von allein – spätestens wenn der JWT abläuft
    oder das Gerät sich abschaltet. Darum wird mit wachsender Wartezeit neu
    verbunden und der Token vor jedem Versuch frisch geholt.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, auth: Any,
                 client: McClient | None = None) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_live", config_entry=entry)
        self._auth = auth
        # Für das Nachladen der Rezeptschritte; ohne Client bleibt der
        # Schritt-Sensor bei der blanken Nummer.
        self._client = client
        self.rezept: dict[str, Any] | None = None   # zuletzt geladenes Rezept
        self._rezept_id: int | None = None          # dessen ID
        self._rezept_task: asyncio.Task | None = None
        self._task: asyncio.Task | None = None
        self.connected = False
        self.device_id: str | None = None
        self.device_model: str | None = None
        self.last_event: datetime | None = None
        self._fremde_modelle: set[str] = set()

    @callback
    def async_start(self) -> None:
        """Hintergrundaufgabe starten (wird mit dem Config-Entry beendet)."""
        if self._task is None and self.config_entry is not None:
            self._task = self.config_entry.async_create_background_task(
                self.hass, self._laufen(), name=f"{DOMAIN}_live_stream"
            )

    async def async_stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    @property
    def stale(self) -> bool:
        """Kam schon länger nichts mehr? Dann ist der Wert nicht mehr frisch."""
        if self.last_event is None:
            return True
        return utcnow() - self.last_event > LIVE_STALE_AFTER

    async def _laufen(self) -> None:
        wartezeit = LIVE_RETRY_START
        erster = True
        while True:
            sauber = False  # Strom ging normal zu Ende (kein Fehler)
            agen = None
            try:
                # Vor jedem **Neu**aufbau einen frischen JWT erzwingen. Sonst
                # liefe der Strom nach langer Geräte-Pause mit abgelaufenem Token
                # ins Leere (``token()`` erneuert von sich aus nur, wenn der
                # Token fehlt, nicht wenn er abgelaufen ist). Beim allerersten
                # Verbinden nutzen wir den gespeicherten Token unverändert.
                if not erster:
                    self._auth.access_token = None
                token = await self._auth.token()
                erster = False
                _LOGGER.debug("MC-Live: verbinde mit %s", GRPC_HOST)
                agen = stream_device_status(
                    token, int(self._auth.user_id or 0), self._auth.companion_app_id
                ).__aiter__()
                while True:
                    # Watchdog: Kommt zu lange nichts, bauen wir neu auf (mit
                    # frischem Token). Zusammen mit dem Keepalive am Kanal fängt
                    # das stillgelegte Verbindungen ab, die sich nach langer
                    # Geräte-Pause sonst nie von selbst erholen.
                    try:
                        meldung = await asyncio.wait_for(
                            agen.__anext__(), timeout=LIVE_WATCHDOG.total_seconds()
                        )
                    except StopAsyncIteration:
                        _LOGGER.debug("MC-Live: Strom regulär beendet")
                        sauber = True
                        break
                    except asyncio.TimeoutError:
                        _LOGGER.debug(
                            "MC-Live: %s ohne Meldung → Neuaufbau mit frischem Token",
                            LIVE_WATCHDOG,
                        )
                        sauber = True
                        break
                    self._verarbeiten(meldung)
                    wartezeit = LIVE_RETRY_START
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 – Strom darf nie HA mitnehmen
                _LOGGER.debug("MC-Live: Strom abgebrochen: %s", err)
            finally:
                if agen is not None:
                    with suppress(Exception):
                        await agen.aclose()
            self.connected = False
            # Ein sauberes Ende (Watchdog/Stream-Ende) ist kein Fehler: kurz
            # warten und neu verbinden, ohne die Wartezeit hochzuziehen. Nur
            # echte Fehler laufen in die wachsende Wartezeit.
            if sauber:
                wartezeit = LIVE_RETRY_START
            await asyncio.sleep(wartezeit)
            if not sauber:
                wartezeit = min(wartezeit * 2, LIVE_RETRY_MAX)

    @callback
    def _verarbeiten(self, meldung: DeviceStatus) -> None:
        """Eine Meldung deuten und an die Entitäten geben."""
        self.device_id = meldung.device_id or self.device_id
        self.device_model = meldung.device_model or self.device_model
        self.connected = meldung.connected
        self.last_event = utcnow()

        # Modell-Schranke: nur der MC3.0 liefert einen Rahmen, den wir deuten
        # können. Andere Modelle werden einmal gemeldet und dann ignoriert.
        modell = meldung.device_model or ""
        if modell and LIVE_MODEL not in modell:
            if modell not in self._fremde_modelle:
                self._fremde_modelle.add(modell)
                _LOGGER.info(
                    "MC-Live: Modell %s wird übersprungen (gedeutet wird nur %s)",
                    modell, LIVE_MODEL,
                )
            return

        status = decode_status(meldung.hex_command or None, meldung.extra_info or None)
        _LOGGER.debug(
            "MC-Live: Quellen=%s Zustand=%s Ist=%s Ziel=%s Stufe=%s Rest=%s%s",
            status.sources, status.command_type, status.current_temp,
            status.target_temp, status.speed, status.remaining_seconds,
            f" Probleme={status.problems}" if status.problems else "",
        )
        self.async_set_updated_data(status)
        self._rezept_sicherstellen(status)

    @callback
    def _rezept_sicherstellen(self, status: DeviceLiveStatus) -> None:
        """Bei Rezeptwechsel die Schritte **einmal** nachladen.

        Der Strom pusht im Sekundentakt – nachgeladen wird deshalb nur, wenn
        sich die Rezept-ID ändert. Das Ergebnis bleibt im Speicher, bis ein
        anderes Rezept läuft.
        """
        rid = status.recipe_id
        if rid is None or rid == self._rezept_id or self._client is None:
            return
        if self._rezept_task is not None and not self._rezept_task.done():
            return
        # ID sofort merken, damit ein zweiter Frame nicht nochmal lädt.
        self._rezept_id = rid
        self.rezept = None
        if self.config_entry is not None:
            self._rezept_task = self.config_entry.async_create_background_task(
                self.hass, self._rezept_laden(rid), name=f"{DOMAIN}_rezept_{rid}"
            )

    async def _rezept_laden(self, recipe_id: int) -> None:
        try:
            self.rezept = await self._client.get_recipe(recipe_id)
        except (McApiError, McAuthError) as err:
            _LOGGER.debug("MC-Live: Rezept %s nicht ladbar: %s", recipe_id, err)
            return
        except Exception as err:  # noqa: BLE001 – darf den Strom nie mitnehmen
            _LOGGER.debug("MC-Live: Rezept %s fehlgeschlagen: %s", recipe_id, err)
            return
        _LOGGER.debug("MC-Live: Rezept %s geladen", recipe_id)
        # Entitäten neu zeichnen – der Status selbst hat sich nicht geändert.
        self.async_update_listeners()
