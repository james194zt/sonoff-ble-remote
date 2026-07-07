# Sonoff BLE Remote

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant custom integration for **Sonoff R5** and **S-Mate** BLE remotes.

Use any ESP32 running **ESPHome** as a BLE relay to decode eWeLink-Remote adverts and forward them to Home Assistant.

## Entity model

Each physical button gets **three toggle binary sensors** — one per click type:

```
Right Lamp Switch
  ├── Top Left Single    →  on / off / on / off  (each single press)
  ├── Top Left Double
  ├── Top Left Long
  ├── Top Centre Single
  ...
```

Every press **flips** the matching entity (`on` ↔ `off`), so Home Assistant and Node-RED always see a real state change — including repeated singles.

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/james194zt/sonoff-ble-remote` as type **Integration**
3. Search **Sonoff BLE Remote** → Install
4. Restart Home Assistant

## Prerequisites

1. **ESPHome** integration installed in Home Assistant
2. An ESP32 node flashed with the BLE relay firmware (see below)
3. The ESPHome node must include `api: homeassistant_services: true`
4. **Enable Home Assistant actions** on the ESPHome device (required for pairing):

   **Settings → Devices & services → ESPHome → BLE RELAY → Configure** → enable **Allow the device to perform Home Assistant actions**

## ESPHome BLE relay

Flash an ESP32 using [`esphome/ble-relay.yaml`](esphome/ble-relay.yaml).

## Add a remote

1. **Settings → Devices & services → Add integration → Sonoff BLE Remote**
2. Select your ESPHome BLE relay
3. Pair or enter device ID manually
4. Choose model and name

## Automations

Toggle a light on each **single** press of Top Left:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.right_lamp_switch_top_left_single
action:
  - service: light.toggle
    target:
      entity_id: light.bedroom_lamp
```

Use `to: "on"` or `to: "off"` if you need direction — odd presses are `on`, even presses are `off`.

Long press example:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.right_lamp_switch_top_left_long
    to: "on"
action:
  - service: light.turn_off
    target:
      area_id: bedroom
```

## Options

**Settings → Devices & services → Sonoff BLE Remote → your remote → Configure**

| Option | Default | Purpose |
|--------|---------|---------|
| **Event deduplication (ms)** | 400 | Collapse R5 BLE rebroadcast bursts |

Also adjustable on the ESPHome device: **Sonoff BLE Event Dedup** number entity.

## Node-RED

Use **events: state** on the click entity you care about:

```
binary_sensor.right_lamp_switch_top_left_single
```

Each single press flips `on` ↔ `off` — Node-RED always triggers.

## License

MIT
