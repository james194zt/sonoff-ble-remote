# Sonoff BLE Remote

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant custom integration for **Sonoff R5** and **S-Mate** BLE remotes, using an [ESPHome ble-relay](https://devices.esphome.io/devices/sonoff-ble/) node to decode eWeLink-Remote adverts.

Each button becomes an **event** entity with **Single Click**, **Double Click**, and **Long Click** — matching the official eWeLink add-on UX.

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/james194zt/sonoff-ble-remote` as type **Integration**
3. Search **Sonoff BLE Remote** → Install
4. Restart Home Assistant

## Prerequisites

An ESPHome node that fires `esphome.sonoff_ble` on the HA event bus. See [ESPHome Sonoff BLE docs](https://devices.esphome.io/devices/sonoff-ble/) or the [HADashboard ble-relay example](https://github.com/james194zt/HADashboard/tree/main/esphome).

## Pair a remote

1. **Settings → Devices & services → Add integration → Sonoff BLE Remote**
2. **Pair — press a button on the remote**
3. Model: **Sonoff R5** (6 buttons) or **S-Mate** (3 buttons)
4. Name it (e.g. `Kitchen R5`)
5. **Submit**, then press any button within 120 seconds

The device ID is captured from ESPHome logs (e.g. `device=0x5acc35c8` → `5acc35c8`).

## Manual device ID

Choose **Enter device ID manually** if you already know the hex ID from ESPHome logs.

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

## Multiple remotes

Add the integration again for each remote (one config entry per device ID).

## Event payload (from ESPHome)

| Field    | Example      |
|----------|--------------|
| `device` | `5acc35c8`   |
| `button` | `1`–`6` (R5) |
| `action` | `short`, `double`, `long` |

## License

MIT
