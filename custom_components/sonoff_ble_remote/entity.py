"""Sonoff BLE Remote — one sensor entity per button (click type as state)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_TO_EVENT,
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_RELAY_NODE,
    DOMAIN,
    MODEL_BUTTONS,
    MODEL_LABELS,
    normalize_device_id,
    normalize_relay_node,
)


class SonoffBleRemoteButton(SensorEntity):
    """One button — state is Single Click, Double Click, or Long Click."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gesture-tap-button"
    _attr_force_update = True

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
        self._entry = entry
        self.button_num = button_num
        remote_key = f"{relay_node}_{device_id}"
        self._attr_unique_id = f"{remote_key}_{button_num}"
        self._attr_name = button_label
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, remote_key)},
            name=device_name,
            manufacturer="SONOFF",
            model=MODEL_LABELS.get(model, model.upper()),
        )
        self._attr_native_value: str | None = None

    @callback
    def trigger_action(self, action: str) -> None:
        event_type = ACTION_TO_EVENT.get(action)
        if event_type is None:
            return
        self._attr_native_value = event_type
        self.async_write_ha_state()


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

    entities = [
        SonoffBleRemoteButton(
            entry, device_id, relay_node, model, name, button_num, button_label
        )
        for button_num, button_label in buttons.items()
    ]
    async_add_entities(entities)

    registry: dict[tuple[str, int], SonoffBleRemoteButton] = hass.data[DOMAIN][
        "entities"
    ]
    for entity in entities:
        registry[(entry.entry_id, entity.button_num)] = entity
