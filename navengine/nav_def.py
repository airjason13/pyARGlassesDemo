
SUPPORTED_NAV_DIRECTIONS = {
    "straight",
    "turn_left",
    "turn_right",
    "turn_slight_left",
    "turn_slight_right",
    "roundabout_enter",
    "roundabout_exit",
    "uturn_left",
    "uturn_right",
    "arrival",
}

ASSET_MAP = {
    "straight": "straight.mp4",
    "turn_left": "turn_left.mp4",
    "turn_right": "turn_right.mp4",
    "turn_slight_left": "slight_left.mp4",
    "turn_slight_right": "slight_right.mp4",
    "roundabout_enter": "roundabout.mp4",
    "roundabout_exit": "straight.mp4",
    "uturn_left": "uturn.mp4",
    "uturn_right": "uturn.mp4",
    "arrival": "arrival.mp4",
}

NAV_HINT_TEXT_MAP = {
    "straight": "↑ Go straight",
    "turn_left": "← Turn left",
    "turn_right": "→ Turn right",
    "turn_slight_left": "↖ Slight left",
    "turn_slight_right": "↗ Slight right",
    "roundabout_enter": "○ Enter roundabout",
    "roundabout_exit": "↑ Exit roundabout",
    "uturn_left": "↺ Make a U-turn (left)",
    "uturn_right": "↻ Make a U-turn (right)",
    "arrival": "◉ You have arrived",
}
