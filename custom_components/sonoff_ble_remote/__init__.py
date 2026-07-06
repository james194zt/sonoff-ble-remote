"""Sonoff BLE Remote integration — R5 / S-Mate via ESPHome ble-relay events."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_ID,
    CONF_RELAY_NODE,
    DOMAIN,
    EVENT_ESPHOME_SONOFF_BLE,
    normalize_device_id,
    normalize_relay_node,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["event"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to include BLE relay selection."""
    if entry.version == 1:
        # Re-pairing is required to select a BLE relay node.
        return False
    return True


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
        for key in list(registry):
            if key[0] == entry.entry_id:
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
    event_node = normalize_relay_node(event.data.get("node", ""))
    if not event_node:
        _LOGGER.debug(
            "Ignored esphome.sonoff_ble event without node field; "
            "update your ESPHome BLE relay firmware"
        )
        return

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
    matched = False

    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_relay = normalize_relay_node(entry.data.get(CONF_RELAY_NODE, ""))
        if entry_relay != event_node:
            continue
        if normalize_device_id(entry.data[CONF_DEVICE_ID]) != device_id:
            continue

        entity = registry.get((entry.entry_id, button))
        if entity is None:
            continue

        entity.trigger_action(action)
        matched = True

    if not matched:
        _LOGGER.debug(
            "Unmatched Sonoff BLE press: relay=%s device=%s button=%s action=%s",
            event_node,
            device_id,
            button,
            action,
        )
