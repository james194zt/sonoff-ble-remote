"""Sonoff BLE Remote integration — R5 / S-Mate via ESPHome ble-relay events."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_ID, DOMAIN, EVENT_ESPHOME_SONOFF_BLE, normalize_device_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["event"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {"entities": {}, "listener": None})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {"entities": {}, "listener": None})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.data[DOMAIN]["listener"] is None:
        hass.data[DOMAIN]["listener"] = hass.bus.async_listen(
            EVENT_ESPHOME_SONOFF_BLE, _make_event_handler(hass)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        registry = hass.data[DOMAIN]["entities"]
        device_id = normalize_device_id(entry.data[CONF_DEVICE_ID])
        for key in list(registry):
            if key[0] == device_id:
                del registry[key]

        if not hass.config_entries.async_entries(DOMAIN):
            if listener := hass.data[DOMAIN].get("listener"):
                listener()
            hass.data.pop(DOMAIN)

    return unload_ok


def _make_event_handler(hass: HomeAssistant):
    @callback
    def handle_event(event) -> None:
        _dispatch_sonoff_ble_event(hass, event)

    return handle_event


@callback
def _dispatch_sonoff_ble_event(hass: HomeAssistant, event) -> None:
    raw_device = event.data.get("device", "")
    device_id = normalize_device_id(raw_device)
    if not device_id:
        return

    try:
        button = int(event.data.get("button", 0))
    except (TypeError, ValueError):
        return

    action = event.data.get("action", "")
    if not action:
        return

    registry = hass.data.get(DOMAIN, {}).get("entities", {})
    entity = registry.get((device_id, button))
    if entity is None:
        _LOGGER.debug(
            "Unpaired Sonoff BLE press: device=%s button=%s action=%s",
            device_id,
            button,
            action,
        )
        return

    entity.trigger_action(action)
