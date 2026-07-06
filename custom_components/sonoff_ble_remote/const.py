DOMAIN = "sonoff_ble_remote"

CONF_DEVICE_ID = "device_id"
CONF_MODEL = "model"
CONF_RELAY_NODE = "relay_node"
CONF_RELAY_DEVICE_ID = "relay_device_id"

ESPHOME_DOMAIN = "esphome"
ESPHOME_DEVICE_NAME = "device_name"

MODEL_R5 = "r5"
MODEL_S_MATE = "s_mate"

EVENT_ESPHOME_SONOFF_BLE = "esphome.sonoff_ble"

PAIR_TIMEOUT_SECONDS = 120

ACTION_TO_EVENT = {
    "short": "Single Click",
    "double": "Double Click",
    "long": "Long Click",
}

R5_BUTTONS: dict[int, str] = {
    1: "Top Left",
    2: "Top Centre",
    3: "Top Right",
    4: "Bottom Left",
    5: "Bottom Centre",
    6: "Bottom Right",
}

S_MATE_BUTTONS: dict[int, str] = {
    1: "Button 1",
    2: "Button 2",
    3: "Button 3",
}

MODEL_BUTTONS = {
    MODEL_R5: R5_BUTTONS,
    MODEL_S_MATE: S_MATE_BUTTONS,
}

MODEL_LABELS = {
    MODEL_R5: "Sonoff R5 (6 buttons)",
    MODEL_S_MATE: "Sonoff S-Mate (3 buttons)",
}


def normalize_device_id(device_id: str) -> str:
    """Normalize hex device id from ESPHome logs or manual entry."""
    return device_id.lower().replace("0x", "").strip()


def normalize_relay_node(relay_node: str) -> str:
    """Normalize ESPHome node slug used in esphome.sonoff_ble events."""
    return relay_node.strip().lower()
