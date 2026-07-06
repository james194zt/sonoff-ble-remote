"""Config flow for Sonoff BLE Remote."""

from __future__ import annotations

import asyncio
import re
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
    MODEL_S_MATE,
    PAIR_TIMEOUT_SECONDS,
    normalize_device_id,
    normalize_relay_node,
)
from .util import get_esphome_device_name, get_esphome_node_from_device_id

DEVICE_ID_RE = re.compile(r"^[0-9a-fA-F]{6,8}$")

METHOD_PAIR = "pair"
METHOD_MANUAL = "manual"


def _known_device_ids(hass: HomeAssistant, relay_node: str) -> set[str]:
    relay_node = normalize_relay_node(relay_node)
    return {
        normalize_device_id(entry.data[CONF_DEVICE_ID])
        for entry in hass.config_entries.async_entries(DOMAIN)
        if normalize_relay_node(entry.data.get(CONF_RELAY_NODE, "")) == relay_node
        and CONF_DEVICE_ID in entry.data
    }


async def _wait_for_sonoff_ble(
    hass: HomeAssistant,
    relay_node: str,
    exclude: set[str],
    timeout: int,
) -> str:
    """Wait for the next esphome.sonoff_ble event from an unknown device."""
    relay_node = normalize_relay_node(relay_node)
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    @callback
    def _handler(event) -> None:
        if normalize_relay_node(event.data.get("node", "")) != relay_node:
            return
        device_id = normalize_device_id(event.data.get("device", ""))
        if not device_id or device_id in exclude:
            return
        if not future.done():
            future.set_result(device_id)

    unsub = hass.bus.async_listen(EVENT_ESPHOME_SONOFF_BLE, _handler)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError:
        raise
    finally:
        unsub()


class SonoffBleRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonoff BLE Remote."""

    VERSION = 2

    def __init__(self) -> None:
        self._model: str = MODEL_R5
        self._name: str = ""
        self._via_manual = False
        self._relay_device_id: str = ""
        self._relay_node: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step: select the ESPHome BLE relay device."""
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
            return await self.async_step_method()

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

    async def async_step_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            method = user_input["method"]
            self._via_manual = method == METHOD_MANUAL
            return await self.async_step_model()

        return self.async_show_form(
            step_id="method",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default=METHOD_PAIR): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=METHOD_PAIR,
                                    label="Pair - press a button on the remote",
                                ),
                                selector.SelectOptionDict(
                                    value=METHOD_MANUAL,
                                    label="Enter device ID manually",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._model = user_input[CONF_MODEL]
            return await self.async_step_name()

        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=MODEL_R5): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=MODEL_R5,
                                    label=MODEL_LABELS[MODEL_R5],
                                ),
                                selector.SelectOptionDict(
                                    value=MODEL_S_MATE,
                                    label=MODEL_LABELS[MODEL_S_MATE],
                                ),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._name = user_input["name"].strip()
            if not self._name:
                return self.async_show_form(
                    step_id="name",
                    errors={"base": "invalid_name"},
                )
            if self._via_manual:
                return await self.async_step_manual()
            return await self.async_step_pair_wait()

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            placeholder="Kitchen R5",
                        )
                    ),
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            device_id = normalize_device_id(user_input[CONF_DEVICE_ID])
            if not DEVICE_ID_RE.match(device_id):
                return self.async_show_form(
                    step_id="manual",
                    errors={"base": "invalid_device_id"},
                )
            if device_id in _known_device_ids(self.hass, self._relay_node):
                return self.async_show_form(
                    step_id="manual",
                    errors={"base": "already_configured"},
                )
            return await self._create_entry(device_id)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            placeholder="5acc35c8",
                        )
                    ),
                }
            ),
        )

    async def async_step_pair_wait(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        relay_name = (
            get_esphome_device_name(self.hass, self._relay_device_id)
            or self._relay_node
        )
        instructions = (
            f"Click Submit, then press any button on the "
            f"{MODEL_LABELS[self._model]} within {PAIR_TIMEOUT_SECONDS} seconds.\n\n"
            f"Listening on ESPHome relay: {relay_name}"
        )

        pair_schema = vol.Schema(
            {
                vol.Required("instructions", default=instructions): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=True,
                        read_only=True,
                    )
                ),
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="pair", data_schema=pair_schema)

        known = _known_device_ids(self.hass, self._relay_node)
        try:
            device_id = await _wait_for_sonoff_ble(
                self.hass, self._relay_node, known, PAIR_TIMEOUT_SECONDS
            )
        except TimeoutError:
            return self.async_show_form(
                step_id="pair",
                errors={"base": "pair_timeout"},
                data_schema=pair_schema,
            )

        return await self._create_entry(device_id)

    async def _create_entry(self, device_id: str) -> FlowResult:
        device_id = normalize_device_id(device_id)
        unique_id = f"{self._relay_node}_{device_id}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._name,
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
