"""Config flow for Sonoff BLE Remote."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_RELAY_DEVICE_ID,
    CONF_RELAY_NODE,
    DOMAIN,
    ESPHOME_DOMAIN,
    EVENT_ESPHOME_SONOFF_BLE,
    MODEL_LABELS,
    MODEL_R5,
    PAIR_TIMEOUT_SECONDS,
    event_matches_relay,
    normalize_device_id,
    normalize_relay_node,
)
from .util import (
    esphome_allows_ha_actions,
    get_esphome_device_name,
    get_esphome_node_from_device_id,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_ID_RE = re.compile(r"^[0-9a-fA-F]{6,8}$")

METHOD_PAIR = "pair"
METHOD_MANUAL = "manual"

METHOD_OPTIONS = {
    METHOD_PAIR: "Pair - press a button on the remote",
    METHOD_MANUAL: "Enter device ID manually",
}


def _known_device_ids(hass: HomeAssistant, relay_node: str) -> set[str]:
    relay_node = normalize_relay_node(relay_node)
    return {
        normalize_device_id(entry.data[CONF_DEVICE_ID])
        for entry in hass.config_entries.async_entries(DOMAIN)
        if normalize_relay_node(entry.data.get(CONF_RELAY_NODE, "")) == relay_node
        and CONF_DEVICE_ID in entry.data
    }


class SonoffBleRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonoff BLE Remote."""

    VERSION = 2

    def __init__(self) -> None:
        self._model: str = MODEL_R5
        self._remote_name: str = ""
        self._via_manual = False
        self._relay_device_id: str = ""
        self._relay_node: str = ""
        self._paired_device_id: str | None = None
        self._pair_unsub: Callable[[], None] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_relay(user_input)

    async def async_step_relay(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._relay_device_id = user_input[CONF_RELAY_DEVICE_ID]
            relay_node = get_esphome_node_from_device_id(
                self.hass, self._relay_device_id
            )
            if relay_node is None:
                return self.async_show_form(
                    step_id="relay",
                    errors={"base": "invalid_relay"},
                    data_schema=self._relay_schema(),
                )
            self._relay_node = relay_node
            return await self.async_step_setup()

        return self.async_show_form(
            step_id="relay",
            data_schema=self._relay_schema(),
        )

    def _relay_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_RELAY_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration=ESPHOME_DOMAIN)
                ),
            }
        )

    def _setup_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("method", default=METHOD_PAIR): vol.In(METHOD_OPTIONS),
                vol.Required(CONF_MODEL, default=MODEL_R5): vol.In(MODEL_LABELS),
                vol.Required("remote_name"): str,
            }
        )

    def _pair_schema(self) -> vol.Schema:
        return vol.Schema({vol.Required("confirm", default=True): bool})

    def _stop_pair_listener(self) -> None:
        if self._pair_unsub is not None:
            self._pair_unsub()
            self._pair_unsub = None

    def _start_pair_listener(self) -> None:
        if self._pair_unsub is not None:
            return

        known = _known_device_ids(self.hass, self._relay_node)
        relay_node = self._relay_node

        @callback
        def _handler(event) -> None:
            data = event.data
            _LOGGER.info("Pairing received %s: %s", EVENT_ESPHOME_SONOFF_BLE, data)

            device_id = normalize_device_id(str(data.get("device", "")))
            if not device_id or device_id in known:
                return

            if not event_matches_relay(data, relay_node, allow_missing_node=True):
                _LOGGER.warning(
                    "Pairing: node mismatch got=%r expected=%r, accepting anyway",
                    data.get("node"),
                    relay_node,
                )

            self._paired_device_id = device_id
            _LOGGER.info("Pairing captured device id %s", device_id)

        self._pair_unsub = self.hass.bus.async_listen(
            EVENT_ESPHOME_SONOFF_BLE, _handler
        )
        _LOGGER.info(
            "Pairing listener started for relay %s (press a button, then Submit)",
            relay_node,
        )

    async def async_step_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._via_manual = user_input["method"] == METHOD_MANUAL
            self._model = user_input[CONF_MODEL]
            self._remote_name = user_input["remote_name"].strip()
            if not self._remote_name:
                return self.async_show_form(
                    step_id="setup",
                    errors={"base": "invalid_name"},
                    data_schema=self._setup_schema(),
                )
            if self._via_manual:
                return await self.async_step_manual()
            return await self.async_step_pair()

        return self.async_show_form(
            step_id="setup",
            data_schema=self._setup_schema(),
        )

    def _manual_schema(self) -> vol.Schema:
        return vol.Schema({vol.Required(CONF_DEVICE_ID): str})

    def _pair_placeholders(self) -> dict[str, str]:
        relay_name = (
            get_esphome_device_name(self.hass, self._relay_device_id)
            or self._relay_node
        )
        captured = (
            f"Detected remote: {self._paired_device_id}"
            if self._paired_device_id
            else "No button press detected yet"
        )
        return {
            "model": MODEL_LABELS.get(self._model, self._model),
            "timeout": str(PAIR_TIMEOUT_SECONDS),
            "relay": relay_name,
            "captured": captured,
        }

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            device_id = normalize_device_id(user_input[CONF_DEVICE_ID])
            if not DEVICE_ID_RE.match(device_id):
                return self.async_show_form(
                    step_id="manual",
                    errors={"base": "invalid_device_id"},
                    data_schema=self._manual_schema(),
                )
            if device_id in _known_device_ids(self.hass, self._relay_node):
                return self.async_show_form(
                    step_id="manual",
                    errors={"base": "already_configured"},
                    data_schema=self._manual_schema(),
                )
            return await self._create_entry(device_id)

        return self.async_show_form(
            step_id="manual",
            data_schema=self._manual_schema(),
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        placeholders = self._pair_placeholders()

        if not esphome_allows_ha_actions(self.hass, self._relay_device_id):
            self._stop_pair_listener()
            return self.async_show_form(
                step_id="pair",
                errors={"base": "ha_actions_disabled"},
                description_placeholders=placeholders,
                data_schema=self._pair_schema(),
            )

        if user_input is None:
            self._paired_device_id = None
            self._start_pair_listener()
            return self.async_show_form(
                step_id="pair",
                description_placeholders=placeholders,
                data_schema=self._pair_schema(),
            )

        self._stop_pair_listener()

        if self._paired_device_id:
            return await self._create_entry(self._paired_device_id)

        return self.async_show_form(
            step_id="pair",
            errors={"base": "pair_timeout"},
            description_placeholders=placeholders,
            data_schema=self._pair_schema(),
        )

    async def _create_entry(self, device_id: str) -> FlowResult:
        self._stop_pair_listener()
        device_id = normalize_device_id(device_id)
        unique_id = f"{self._relay_node}_{device_id}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._remote_name,
            data={
                CONF_DEVICE_ID: device_id,
                CONF_MODEL: self._model,
                CONF_RELAY_NODE: self._relay_node,
                CONF_RELAY_DEVICE_ID: self._relay_device_id,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return SonoffBleRemoteOptionsFlowHandler(config_entry)


class SonoffBleRemoteOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow placeholder — add more remotes via Add Integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_show_form(step_id="init")
