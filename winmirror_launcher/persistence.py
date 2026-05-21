import json
from pathlib import Path


DEFAULT_STATE = {
    "state_version": 3,
    "layout_mode": "horizontal",
    "panel_mode": "floating",
    "anchor_edge": "top",
    "show_workspace_badge": False,
    "show_title": False,
    "show_close_button": False,
    "hover_expand_enabled": False,
    "refresh_mode": "live",
    "refresh_interval_ms": 1000,
    "tile_width": 120,
    "tile_height": 78,
    "panel_spacing": 4,
    "geometry": {
        "x": None,
        "y": None,
        "width": 760,
        "height": 104,
    },
    "simple_panel": {
        "tile_width": 120,
        "tile_height": 72,
        "fps": 1.0,
        "mirror_layout_mode": "grid",
        "window_decorated": False,
        "show_title": False,
        "show_close": False,
        "show_workspace": False,
        "hover_mode": "off",
        "hover_scale": 1.0,
        "show_borders": False,
        "order_mode": "last-used",
        "label_mode": "title",
        "sticky_workspaces": False,
        "idle_mode": "off",
        "idle_delay_ms": 700,
        "frame_interval_seconds": None,
        "show_clock": False,
        "clock_mode": "date-time",
        "clock_font_size": 10,
        "clock_font_color": "#e6ebf0",
        "clock_show_weather": False,
        "clock_show_precipitation": False,
        "clock_weather_location": "",
        "background_color": "#000000",
        "background_alpha": 0.0,
        "show_tint2": False,
        "show_launchers": True,
        "launcher_units": 4,
        "tint2_profile": "default",
        "tint2_units": 2,
        "tint2_placement": "cell",
        "tint2_take_systray": False,
        "geometry": {
            "x": None,
            "y": None,
            "width": 760,
            "height": 104,
        },
    },
    "tile_order": [],
}

MIN_TILE_WIDTH = 88
MAX_TILE_WIDTH = 220
MIN_TILE_HEIGHT = 60
MAX_TILE_HEIGHT = 160
MIN_PANEL_SPACING = 2
MAX_PANEL_SPACING = 16
MIN_PANEL_WIDTH = 360
MAX_PANEL_WIDTH = 1400
MIN_PANEL_HEIGHT = 84
MAX_PANEL_HEIGHT = 520


def clamp_int(value, lower, upper, fallback):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(lower, min(upper, value))


class StateStore:
    def __init__(self, path=None):
        self.path = Path(path or Path.home() / ".config" / "winmirror-launcher" / "state.json")

    def load(self):
        if not self.path.exists():
            return self._copy_default()

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._copy_default()

        if not isinstance(data, dict):
            return self._copy_default()

        version = data.get("state_version")
        if not isinstance(version, int) or version < DEFAULT_STATE["state_version"]:
            state = self._copy_default()
            tile_order = data.get("tile_order")
            if isinstance(tile_order, list):
                state["tile_order"] = [int(item) for item in tile_order if isinstance(item, int)]
            return state

        state = self._copy_default()
        state.update({k: v for k, v in data.items() if k in state})
        geometry = data.get("geometry") if isinstance(data, dict) else None
        if isinstance(geometry, dict):
            state["geometry"].update(
                {k: geometry.get(k) for k in state["geometry"].keys() if k in geometry}
            )

        simple_panel = data.get("simple_panel") if isinstance(data, dict) else None
        if isinstance(simple_panel, dict):
            state["simple_panel"].update(
                {k: v for k, v in simple_panel.items() if k in state["simple_panel"] and k != "geometry"}
            )
            simple_geometry = simple_panel.get("geometry")
            if isinstance(simple_geometry, dict):
                state["simple_panel"]["geometry"].update(
                    {
                        k: simple_geometry.get(k)
                        for k in state["simple_panel"]["geometry"].keys()
                        if k in simple_geometry
                    }
                )

        tile_order = data.get("tile_order") if isinstance(data, dict) else None
        if isinstance(tile_order, list):
            state["tile_order"] = [int(item) for item in tile_order if isinstance(item, int)]

        if not isinstance(state.get("state_version"), int):
            state["state_version"] = DEFAULT_STATE["state_version"]

        state["tile_width"] = clamp_int(
            state.get("tile_width"),
            MIN_TILE_WIDTH,
            MAX_TILE_WIDTH,
            DEFAULT_STATE["tile_width"],
        )
        state["tile_height"] = clamp_int(
            state.get("tile_height"),
            MIN_TILE_HEIGHT,
            MAX_TILE_HEIGHT,
            DEFAULT_STATE["tile_height"],
        )
        state["panel_spacing"] = clamp_int(
            state.get("panel_spacing"),
            MIN_PANEL_SPACING,
            MAX_PANEL_SPACING,
            DEFAULT_STATE["panel_spacing"],
        )
        state["geometry"]["width"] = clamp_int(
            state["geometry"].get("width"),
            MIN_PANEL_WIDTH,
            MAX_PANEL_WIDTH,
            DEFAULT_STATE["geometry"]["width"],
        )
        state["geometry"]["height"] = clamp_int(
            state["geometry"].get("height"),
            MIN_PANEL_HEIGHT,
            MAX_PANEL_HEIGHT,
            DEFAULT_STATE["geometry"]["height"],
        )

        return state

    def save(self, state):
        payload = self._copy_default()
        payload.update({k: v for k, v in state.items() if k in payload})
        payload["state_version"] = DEFAULT_STATE["state_version"]
        geometry = state.get("geometry") if isinstance(state.get("geometry"), dict) else {}
        payload["geometry"].update(
            {k: geometry.get(k) for k in payload["geometry"].keys() if k in geometry}
        )
        simple_panel = state.get("simple_panel") if isinstance(state.get("simple_panel"), dict) else {}
        payload["simple_panel"].update(
            {k: v for k, v in simple_panel.items() if k in payload["simple_panel"] and k != "geometry"}
        )
        simple_geometry = simple_panel.get("geometry") if isinstance(simple_panel.get("geometry"), dict) else {}
        payload["simple_panel"]["geometry"].update(
            {
                k: simple_geometry.get(k)
                for k in payload["simple_panel"]["geometry"].keys()
                if k in simple_geometry
            }
        )
        payload["tile_order"] = [int(item) for item in state.get("tile_order", [])]

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _copy_default(self):
        return {
            "state_version": DEFAULT_STATE["state_version"],
            "layout_mode": DEFAULT_STATE["layout_mode"],
            "panel_mode": DEFAULT_STATE["panel_mode"],
            "anchor_edge": DEFAULT_STATE["anchor_edge"],
            "show_workspace_badge": DEFAULT_STATE["show_workspace_badge"],
            "show_title": DEFAULT_STATE["show_title"],
            "show_close_button": DEFAULT_STATE["show_close_button"],
            "hover_expand_enabled": DEFAULT_STATE["hover_expand_enabled"],
            "refresh_mode": DEFAULT_STATE["refresh_mode"],
            "refresh_interval_ms": DEFAULT_STATE["refresh_interval_ms"],
            "tile_width": DEFAULT_STATE["tile_width"],
            "tile_height": DEFAULT_STATE["tile_height"],
            "panel_spacing": DEFAULT_STATE["panel_spacing"],
            "geometry": dict(DEFAULT_STATE["geometry"]),
            "simple_panel": {
                **{k: v for k, v in DEFAULT_STATE["simple_panel"].items() if k != "geometry"},
                "geometry": dict(DEFAULT_STATE["simple_panel"]["geometry"]),
            },
            "tile_order": list(DEFAULT_STATE["tile_order"]),
        }
