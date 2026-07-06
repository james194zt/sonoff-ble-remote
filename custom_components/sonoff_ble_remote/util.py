"""Helpers for Sonoff BLE Remote."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import ESPHOME_DEVICE_NAME, ESPHOME_DOMAIN, normalize_relay_node

CONNECTION_NETWORK_MAC = "mac"


def _device_mac(device: dr.DeviceEntry) -> str | None:
    """Return normalized MAC from a device registry entry."""
    for conn_type, conn_id in device.connections:
        if conn_type == CONNECTION_NETWORK_MAC:
            return conn_id.lower()
    return None


def _resolve_root_esphome_device(
    registry: dr.DeviceRegistry, device_id: str
) -> dr.DeviceEntry | None:
    """Return the root ESPHome device (walk up via_device chain)."""
    device = registry.async_get(device_id)
    if device is None:
        return None

    visited: set[str] = set()
    while device.via_device_id and device.via_device_id not in visited:
        visited.add(device.id)
        parent = registry.async_get(device.via_device_id)
        if parent is None:
            break
        device = parent

    return device


def _node_from_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Return ESPHome node slug from a config entry."""
    name = entry.data.get(ESPHOME_DEVICE_NAME)
    if name:
        return normalize_relay_node(str(name))

    runtime = getattr(entry, "runtime_data", None)
    device_info = getattr(runtime, "device_info", None)
    if device_info and getattr(device_info, "name", None):
        return normalize_relay_node(str(device_info.name))

    return None


def _node_from_esphome_config_entries(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> str | None:
    """Resolve node name from config entries linked to the device."""
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != ESPHOME_DOMAIN:
            continue
        node = _node_from_config_entry(hass, entry)
        if node:
            return node
    return None


def _node_from_esphome_entries_by_mac(
    hass: HomeAssistant, mac: str
) -> str | None:
    """Fallback: match ESPHome config entry by device MAC."""
    mac = mac.lower()
    registry = dr.async_get(hass)

    for entry in hass.config_entries.async_entries(ESPHOME_DOMAIN):
        for dev_id in dr.async_entries_for_config_entry(registry, entry.entry_id):
            device = registry.async_get(dev_id)
            if device and _device_mac(device) == mac:
                node = _node_from_config_entry(hass, entry)
                if node:
                    return node

    return None


def get_esphome_node_from_device_id(
    hass: HomeAssistant, device_id: str
) -> str | None:
    """Return the ESPHome node slug for a device registry device id."""
    registry = dr.async_get(hass)
    device = _resolve_root_esphome_device(registry, device_id)
    if device is None:
        return None

    # Sub-devices may have (esphome, mac_suffix) identifiers — not the node name.
    node = _node_from_esphome_config_entries(hass, device)
    if node:
        return node

    # ESPHome main devices use MAC connections, not esphome identifiers.
    if mac := _device_mac(device):
        return _node_from_esphome_entries_by_mac(hass, mac)

    return None


def get_esphome_device_name(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the friendly name of an ESPHome device."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        return None
    return device.name_by_user or device.name
