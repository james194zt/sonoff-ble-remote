"""Event entities for Sonoff BLE Remote buttons."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_TO_EVENT,
    CONF_DEVICE_ID,
    CONF_MODEL,
    DOMAIN,
    MODEL_BUTTONS,
    MODEL_LABELS,
    normalize_device_id,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_id = normalize_device_id(entry.data[CONF_DEVICE_ID])
    model = entry.data[CONF_MODEL]
    name = entry.title
    buttons = MODEL_BUTTONS[model]

    entities = [
        SonoffBleRemoteButton(
            entry,
            device_id,
            model,
            name,
            button_num,
            button_label,
        )
        for button_num, button_label in buttons.items()
    ]
    async_add_entities(entities)

    registry: dict[tuple[str, int], SonoffBleRemoteButton] = hass.data[DOMAIN][
        "entities"
    ]
    for entity in entities:
        registry[(device_id, entity.button_num)] = entity


class SonoffBleRemoteButton(EventEntity):
    """A Sonoff BLE remote button (short / double / long press)."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = list(ACTION_TO_EVENT.values())
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        device_id: str,
        model: str,
        device_name: str,
        button_num: int,
        button_label: str,
    ) -> None:
        self._entry = entry
        self._device_id = device_id.lower()
        self._model = model
        self.button_num = button_num

        self._attr_unique_id = f"{device_id}_{button_num}"
        self._attr_name = button_label
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="SONOFF",
            model=MODEL_LABELS.get(model, model.upper()),
        )

    @callback
    def trigger_action(self, action: str) -> None:
        """Fire the matching click event type."""
        event_type = ACTION_TO_EVENT.get(action)
        if event_type is None:
            return
        self._trigger_event(event_type)
