"""Sonoff BLE Remote integration — R5 / S-Mate via ESPHome ble-relay events."""

from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION_KEYS,
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_RELAY_NODE,
    CONF_DEBOUNCE_MS,
    DEFAULT_DEBOUNCE_MS,
    DOMAIN,
    EVENT_ESPHOME_SONOFF_BLE,
    event_matches_relay,
    get_debounce_seconds,
    map_r5_ble_button,
    normalize_device_id,
    normalize_relay_node,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]

LEGACY_BINARY_SUFFIXES = ("_toggle", "_press", "_click")
CURRENT_BINARY_SUFFIXES = tuple(f"_{key}" for key in ACTION_KEYS.values())

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def _async_cleanup_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove orphaned entities left from older integration versions."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain in ("event", "sensor"):
            _LOGGER.info("Removing legacy %s entity %s", entity.domain, entity.entity_id)
            registry.async_remove(entity.entity_id)
            continue
        if entity.domain != "binary_sensor":
            continue
        unique_id = entity.unique_id or ""
        if unique_id.endswith(LEGACY_BINARY_SUFFIXES):
            _LOGGER.info("Removing legacy binary_sensor %s", entity.entity_id)
            registry.async_remove(entity.entity_id)
            continue
        if not unique_id.endswith(CURRENT_BINARY_SUFFIXES):
            _LOGGER.info("Removing orphan binary_sensor %s", entity.entity_id)
            registry.async_remove(entity.entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to include BLE relay selection."""
    if entry.version == 1:
        return False
    return True


def _configured_relay_nodes(hass: HomeAssistant) -> set[str]:
    return {
        normalize_relay_node(entry.data[CONF_RELAY_NODE])
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_RELAY_NODE)
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(
        DOMAIN, {"entities": {}, "listener": None, "debounce": {}}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(
        DOMAIN, {"entities": {}, "listener": None, "debounce": {}}
    )

    _async_cleanup_stale_entities(hass, entry)

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

        debounce = hass.data[DOMAIN].get("debounce", {})
        for key in list(debounce):
            if key[0] == entry.entry_id:
                del debounce[key]

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
    data = event.data
    allow_missing_node = len(_configured_relay_nodes(hass)) <= 1

    raw_device = data.get("device", "")
    device_id = normalize_device_id(str(raw_device))
    if not device_id:
        return

    try:
        button = int(data.get("button", 0))
    except (TypeError, ValueError):
        return

    action = data.get("action", "")
    if not action:
        return

    registry = hass.data.get(DOMAIN, {}).get("entities", {})
    debounce_store: dict[tuple[str, int, str], float] = hass.data[DOMAIN].setdefault(
        "debounce", {}
    )
    now = time.monotonic()
    matched = False

    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_relay = normalize_relay_node(entry.data.get(CONF_RELAY_NODE, ""))
        if not event_matches_relay(
            data, entry_relay, allow_missing_node=allow_missing_node
        ):
            continue
        if normalize_device_id(entry.data[CONF_DEVICE_ID]) != device_id:
            continue

        button = map_r5_ble_button(button, entry.data.get(CONF_MODEL, ""))

        entity = registry.get((entry.entry_id, button))
        if entity is None:
            continue

        debounce_key = (entry.entry_id, button, action)
        debounce_seconds = get_debounce_seconds(entry)
        if (prev := debounce_store.get(debounce_key)) is not None:
            if (now - prev) < debounce_seconds:
                _LOGGER.debug(
                    "Debounced rebroadcast: device=%s button=%s action=%s",
                    device_id,
                    button,
                    action,
                )
                matched = True
                continue

        debounce_store[debounce_key] = now
        entity.trigger_action(action)
        matched = True

    if not matched:
        _LOGGER.debug(
            "Unmatched Sonoff BLE press: node=%s device=%s button=%s action=%s",
            data.get("node"),
            device_id,
            button,
            action,
        )
