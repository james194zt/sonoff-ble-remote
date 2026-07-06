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
4. **Enable Home Assistant actions** on the ESPHome device (required for pairing):

   **Settings → Devices & services → ESPHome → BLE RELAY → Configure** → enable **Allow the device to perform Home Assistant actions**

   Without this, button presses appear in ESPHome logs but never reach Home Assistant.

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

### Options

**Settings → Devices & services → Sonoff BLE Remote → your remote → Configure**

| Option | Default | Purpose |
|--------|---------|---------|
| **Event deduplication (ms)** | 400 | Ignore duplicate events for the same button within this window |

Increase if one physical press still triggers twice in HA/Node-RED. Decrease if repeat presses on the same button feel sluggish. This only affects the Home Assistant integration — ESPHome firmware has a separate 400 ms filter in `sonoff_ble_receiver.yaml`.

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

## Event latency

Nothing is **polled** in Home Assistant — the chain is:

```
R5 press → BLE advert → ESP32 scan → esphome.sonoff_ble → HA entity (instant)
```

### Where the delay comes from

| Source | Typical delay | Can we fix it? |
|--------|---------------|----------------|
| **R5 “short” detection** | ~300–500 ms | **No** — remote waits to see if you double/long press |
| ESP32 BLE scan | ~50–150 ms | Reflash with 80 ms scan window (see below) |
| Duplicate-advert filter | 400 ms per button | Reflash ble-relay |
| Home Assistant | ~instant | Already event-driven |

The **R5 does not send a “button down” event**. It only BLE-adverts after it has decided the press type (`short`, `double`, or `long`). That is why a light switch feels slightly sluggish compared to a wired switch — it is the remote, not HA polling.

The official eWeLink gateway uses a ~**400 ms** decision window for the same reason.

### ESPHome tuning (reflash ble-relay)

Latest `sonoff_ble_receiver.yaml` uses:

- **80 ms** scan interval/window (near-continuous active scan)
- **Always-on** scanning from boot (no stop when API drops)
- **400 ms** per-button dedup (R5 rebroadcasts 2–3 BLE adverts per physical press)

### Automation tips for lights

Use **Single Click** and keep the automation fast:

```yaml
trigger:
  - platform: state
    entity_id: event.kitchen_r5_bottom_centre
    attribute: event_type
    to: Single Click
mode: restart
action:
  - service: light.toggle
    target:
      entity_id: light.kitchen
```

- Use `mode: restart` (not `queued`) so rapid presses are not stacked
- Do **not** add an extra `delay` in the automation
- Map only the buttons you need to **Single Click** for lights

### Rapid presses / multiple lights in one room

The **R5 will not send a second press while it is still deciding the first one**
(~300–500 ms per button). Hammering four buttons in under half a second will
often drop presses — that is remote firmware, not Home Assistant.

**What you can do:**

1. **Pace presses** — leave ~½ second between each button when turning off several lights.
2. **One button → scene/script** — map one button (or a **Long Click**) to turn off every light in the room:

```yaml
action:
  - service: light.turn_off
    target:
      entity_id:
        - light.ceiling
        - light.lamp_left
        - light.lamp_right
```

3. **Reflash ble-relay** — latest decoder uses 400 ms per-button dedup and 80 ms continuous BLE scan.

### Measuring latency

Compare timestamps in **ESPHome log** vs **Developer tools → Events** for `esphome.sonoff_ble`. If ESPHome logs the press quickly but HA is slow, the issue is HA-side. If ESPHome log itself is delayed after your physical press, the R5 + BLE scan path is the bottleneck.

### Node-RED

One **`event.*` entity per button** — same model as the official eWeLink addon.
Dedup (ESPHome + integration) ensures **one update per physical press**.

Listen for `state_changed` on the event entity and read the press type from
**`event_type`** in attributes (not from `state`, which is a timestamp):

```
msg.data.new_state.attributes.event_type  →  "Single Click" | "Double Click" | "Long Click"
```

Each press updates the timestamp in `state`, so Node-RED always sees a change
even when the same button sends the same click type twice in a row.

## License

MIT
