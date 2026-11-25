"""The Timers sensor: what the clock should show. Its attributes are a stable format other things can follow.

Also Signal strength: the live Bluetooth link's RSSI, for a paired clock."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EchoWallClockConfigEntry
from .const import CONF_ADAPTER, CONF_ADDRESS
from .entity import ClockEntity

FORMAT_VERSION = 1
SCAN_INTERVAL = timedelta(seconds=60)
"""How often Signal strength reads the link's RSSI. The Timers sensor doesn't poll."""


async def async_setup_entry(
    hass: HomeAssistant, entry: EchoWallClockConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    entities: list[SensorEntity] = [TimersSensor(entry)]
    if entry.runtime_data.has_link:
        entities.append(SignalSensor(entry))
    async_add_entities(entities)


class TimersSensor(ClockEntity, SensorEntity):
    """Number of timers the clock should know about, with the list in attributes."""

    def __init__(self, entry: EchoWallClockConfigEntry) -> None:
        super().__init__(entry, "timers")

    @property
    def native_value(self) -> int:
        return len(self._controller.timers)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        timers = sorted(
            self._controller.timers.values(), key=lambda t: (t.ends_at is None, t.ends_at or 0, t.key)
        )
        return {
            "format": FORMAT_VERSION,
            "timers": [
                {
                    "id": t.key,
                    "token": t.token,
                    "name": t.name,
                    "ends_at": t.ends_at.replace(microsecond=0).isoformat() if t.ends_at else None,
                    "paused": t.paused,
                }
                for t in timers
            ],
        }


class SignalSensor(ClockEntity, SensorEntity):
    """RSSI of the live link in dB: 0 is inside the radio's ideal receive range, below 0 is weaker."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
    _attr_should_poll = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: EchoWallClockConfigEntry) -> None:
        super().__init__(entry, "signal_strength")
        self._adapter: str = entry.data[CONF_ADAPTER]
        self._address: str = entry.data[CONF_ADDRESS]

    @property
    def available(self) -> bool:
        return self._controller.connected

    async def async_update(self) -> None:
        from .bluez import read_rssi  # Linux only

        self._attr_native_value = await read_rssi(self._adapter, self._address) if self._controller.connected else None

    def _updated(self) -> None:
        if not self._controller.connected:
            self._attr_native_value = None
        super()._updated()
