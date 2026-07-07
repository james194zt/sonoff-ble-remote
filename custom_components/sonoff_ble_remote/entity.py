"""Sonoff BLE Remote — three toggle binary_sensors per button (Single/Double/Long)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_KEYS,
    ACTION_LABELS,
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_RELAY_NODE,
    DOMAIN,
    MODEL_BUTTONS,
    MODEL_LABELS,
    normalize_device_id,
    normalize_relay_node,
)


class SonoffBleRemoteClickToggle(BinarySensorEntity):
    """Toggles on/off each time this click type is pressed on the button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        relay_node: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
        action: str,
    ) -> None:
        self.button_num = button_num
        self._action = action
        remote_key = f"{relay_node}_{device_id}"
        self._attr_unique_id = f"{remote_key}_{button_num}_{ACTION_KEYS[action]}"
        self._attr_name = f"{button_label} {ACTION_LABELS[action]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, remote_key)},
            name=device_name,
            manufacturer="SONOFF",
            model=MODEL_LABELS.get(model, model.upper()),
        )
        self._attr_is_on = False

    @callback
    def press(self) -> None:
        """Flip on/off — every press changes state for HA and Node-RED."""
        self._attr_is_on = not self._attr_is_on
        self.async_write_ha_state()


class SonoffBleRemoteButton:
    """One physical button — Single, Double, and Long click toggles."""

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
        self.single = SonoffBleRemoteClickToggle(
            device_id, relay_node, model, device_name, button_num, button_label, "short"
        )
        self.double = SonoffBleRemoteClickToggle(
            device_id, relay_node, model, device_name, button_num, button_label, "double"
        )
        self.long = SonoffBleRemoteClickToggle(
            device_id, relay_node, model, device_name, button_num, button_label, "long"
        )
        self._clicks = {
            "short": self.single,
            "double": self.double,
            "long": self.long,
        }

    @property
    def entities(self) -> list[BinarySensorEntity]:
        return [self.single, self.double, self.long]

    @callback
    def trigger_action(self, action: str) -> None:
        click = self._clicks.get(action)
        if click is not None:
            click.press()


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
    entities: list[BinarySensorEntity] = []
    for pair in pairs:
        entities.extend(pair.entities)
    async_add_entities(entities)

    registry: dict[tuple[str, int], SonoffBleRemoteButton] = hass.data[DOMAIN][
        "entities"
    ]
    for pair in pairs:
        registry[(entry.entry_id, pair.button_num)] = pair
