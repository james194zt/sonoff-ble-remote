"""Sonoff BLE Remote button entities (event + sensor + toggle + pulse per button)."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    ACTION_TO_EVENT,
    ACTION_TO_SENSOR,
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_RELAY_NODE,
    DOMAIN,
    MODEL_BUTTONS,
    MODEL_LABELS,
    normalize_device_id,
    normalize_relay_node,
)

_LOGGER = logging.getLogger(__name__)

PULSE_SECONDS = 0.2  # Node-RED needs ~25 ms; hold ON long enough to catch it


class SonoffBleRemoteButton:
    """Event, click sensor, toggle, and pulse binary_sensor for one remote button."""

    def __init__(
        self,
        entry: ConfigEntry,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        self.button_num = button_num
        self.event = SonoffBleRemoteButtonEvent(
            device_id, relay_node, model, device_name, button_num, button_label
        )
        self.sensor = SonoffBleRemoteButtonSensor(
            device_id, relay_node, model, device_name, button_num, button_label
        )
        self.toggle = SonoffBleRemoteButtonToggle(
            device_id, relay_node, model, device_name, button_num, button_label
        )
        self.pulse = SonoffBleRemoteButtonPulse(
            device_id, relay_node, model, device_name, button_num, button_label
        )

    @callback
    def trigger_action(self, action: str) -> None:
        """Fire event entity and update sensor / toggle / pulse state."""
        self.event.trigger_action(action)
        self.sensor.trigger_action(action)
        self.toggle.trigger_action(action)
        self.pulse.trigger_action(action)


class SonoffBleRemoteButtonEvent(EventEntity):
    """HA event entity — for automations/device triggers."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = list(ACTION_TO_EVENT.values())
    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        remote_key = f"{relay_node}_{device_id}"
        self.button_num = button_num
        self._attr_unique_id = f"{remote_key}_{button_num}"
        self._attr_name = button_label
        self._attr_device_info = _device_info(remote_key, device_name, model)

    @callback
    def trigger_action(self, action: str) -> None:
        event_type = ACTION_TO_EVENT.get(action)
        if event_type is None:
            return
        self._trigger_event(event_type)


class SonoffBleRemoteButtonSensor(SensorEntity):
    """Last click type; press_count attribute increments on every press."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(
        self,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        remote_key = f"{relay_node}_{device_id}"
        self.button_num = button_num
        self._press_count = 0
        self._attr_unique_id = f"{remote_key}_{button_num}_click"
        self._attr_name = f"{button_label} Click"
        self._attr_device_info = _device_info(remote_key, device_name, model)
        self._attr_native_value: str | None = None
        self._attr_extra_state_attributes: dict[str, int | str] = {"press_count": 0}

    @callback
    def trigger_action(self, action: str) -> None:
        click = ACTION_TO_SENSOR.get(action)
        if click is None:
            return
        self._press_count += 1
        self._attr_native_value = click
        self._attr_extra_state_attributes = {
            "click": click,
            "press_count": self._press_count,
        }
        self.async_write_ha_state()


class SonoffBleRemoteButtonToggle(BinarySensorEntity):
    """Toggles on/off on each single click — for on/off light state."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:toggle-switch"

    def __init__(
        self,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        remote_key = f"{relay_node}_{device_id}"
        self.button_num = button_num
        self._attr_unique_id = f"{remote_key}_{button_num}_toggle"
        self._attr_name = f"{button_label} Toggle"
        self._attr_device_info = _device_info(remote_key, device_name, model)
        self._attr_is_on = False

    @callback
    def trigger_action(self, action: str) -> None:
        if action != "short":
            return
        self._attr_is_on = not self._attr_is_on
        self.async_write_ha_state()


class SonoffBleRemoteButtonPulse(BinarySensorEntity):
    """Momentary ON pulse (200 ms) on each press — for Node-RED state triggers."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gesture-tap"

    def __init__(
        self,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        remote_key = f"{relay_node}_{device_id}"
        self.button_num = button_num
        self._attr_unique_id = f"{remote_key}_{button_num}_press"
        self._attr_name = f"{button_label} Press"
        self._attr_device_info = _device_info(remote_key, device_name, model)
        self._attr_is_on = False
        self._unsub_pulse: Callable[[], None] | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending pulse when entity is removed."""
        self._async_cancel_pulse()

    @callback
    def _async_cancel_pulse(self) -> None:
        if self._unsub_pulse is not None:
            self._unsub_pulse()
            self._unsub_pulse = None

    @callback
    def _async_pulse_off(self, _now) -> None:
        self._unsub_pulse = None
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def trigger_action(self, action: str) -> None:
        if action not in ACTION_TO_SENSOR:
            return
        self._async_cancel_pulse()
        self._attr_is_on = True
        self.async_write_ha_state()
        self._unsub_pulse = async_call_later(
            self.hass, PULSE_SECONDS, self._async_pulse_off
        )


def _device_info(remote_key: str, device_name: str, model: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, remote_key)},
        name=device_name,
        manufacturer="SONOFF",
        model=MODEL_LABELS.get(model, model.upper()),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_id = normalize_device_id(entry.data[CONF_DEVICE_ID])
    relay_node = normalize_relay_node(entry.data[CONF_RELAY_NODE])
    model = entry.data[CONF_MODEL]
    name = entry.title
    buttons = MODEL_BUTTONS[model]

    pairs = [
        SonoffBleRemoteButton(
            entry, device_id, relay_node, model, name, button_num, button_label
        )
        for button_num, button_label in buttons.items()
    ]
    entities: list[EventEntity | SensorEntity | BinarySensorEntity] = []
    for pair in pairs:
        entities.append(pair.event)
        entities.append(pair.sensor)
        entities.append(pair.toggle)
        entities.append(pair.pulse)
    async_add_entities(entities)

    registry: dict[tuple[str, int], SonoffBleRemoteButton] = hass.data[DOMAIN][
        "entities"
    ]
    for pair in pairs:
        registry[(entry.entry_id, pair.button_num)] = pair
