# Sonoff BLE Remote

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant custom integration for **Sonoff R5** and **S-Mate** BLE remotes.

Use any ESP32 running **ESPHome** as a BLE relay to decode eWeLink-Remote adverts and forward them to Home Assistant. Each remote button becomes an **event** entity with **Single Click**, **Double Click**, and **Long Click**.

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/james194zt/sonoff-ble-remote` as type **Integration**
3. Search **Sonoff BLE Remote** → Install
4. Restart Home Assistant

## Prerequisites

1. **ESPHome** integration installed in Home Assistant
2. An ESP32 node flashed with the BLE relay firmware (see below)
3. The ESPHome node must include `api: homeassistant_services: true`

### ESPHome BLE relay

Flash an ESP32 using the example in [`esphome/ble-relay.yaml`](esphome/ble-relay.yaml), or add the Sonoff BLE decoder from the [ESPHome docs](https://devices.esphome.io/devices/sonoff-ble/).

**Important:** Events must include a `node` field (the ESPHome device name). The example firmware in this repo does this automatically via `App.get_name()`. Reflash if you use an older YAML without the `node` field.

## Add a remote

1. **Settings → Devices & services → Add integration → Sonoff BLE Remote**
2. **Select your ESPHome BLE relay** from the device list
3. Choose **Pair** or **Enter device ID manually**
4. Select model (**R5** = 6 buttons, **S-Mate** = 3 buttons)
5. Name the remote (e.g. `Kitchen R5`)
6. If pairing: **Submit**, then press any button within 120 seconds

The Sonoff remote links to the selected ESPHome relay. Multiple relays and multiple remotes are supported.

## Automations

```yaml
trigger:
  - platform: state
    entity_id: event.kitchen_r5_bottom_centre
    attribute: event_type
    to: Long Click
action:
  - service: light.toggle
    target:
      entity_id: light.kitchen
```

Or use **Device triggers** in the UI.

## Event payload (from ESPHome)

| Field    | Example      | Description                          |
|----------|--------------|--------------------------------------|
| `node`   | `ble-relay`  | ESPHome device name (BLE relay)      |
| `device` | `5acc35c8`   | Sonoff remote ID                     |
| `button` | `1`–`6` (R5) | Button number                        |
| `action` | `short`      | `short`, `double`, or `long`         |

## Multiple remotes / relays

- Add the integration again for each Sonoff remote
- Select the correct ESPHome relay if you have more than one
- The same Sonoff remote ID can exist on different relays independently

## License

MIT
