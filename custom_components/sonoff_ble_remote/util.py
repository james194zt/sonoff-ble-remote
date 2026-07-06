"""Helpers for Sonoff BLE Remote."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import ESPHOME_DOMAIN, normalize_relay_node


def get_esphome_node_from_device_id(
    hass: HomeAssistant, device_id: str
) -> str | None:
    """Return the ESPHome node slug for a device registry device id."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        return None

    for domain, identifier in device.identifiers:
        if domain == ESPHOME_DOMAIN:
            return normalize_relay_node(identifier)

    return None


def get_esphome_device_name(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the friendly name of an ESPHome device."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        return None
    return device.name_by_user or device.name
