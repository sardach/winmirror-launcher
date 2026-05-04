import json
from pathlib import Path


DEFAULT_STATE = {
    "state_version": 2,
    "layout_mode": "horizontal",
    "panel_mode": "floating",
    "anchor_edge": "top",
    "show_workspace_badge": False,
    "show_title": False,
    "show_close_button": False,
    "hover_expand_enabled": False,
    "refresh_mode": "live",
    "refresh_interval_ms": 1000,
    "tile_width": 156,
    "tile_height": 96,
    "panel_spacing": 6,
    "geometry": {
        "x": None,
        "y": None,
        "width": 900,
        "height": 132,
    },
    "tile_order": [],
}


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

        tile_order = data.get("tile_order") if isinstance(data, dict) else None
        if isinstance(tile_order, list):
            state["tile_order"] = [int(item) for item in tile_order if isinstance(item, int)]

        if not isinstance(state.get("state_version"), int):
            state["state_version"] = DEFAULT_STATE["state_version"]

        return state

    def save(self, state):
        payload = self._copy_default()
        payload.update({k: v for k, v in state.items() if k in payload})
        geometry = state.get("geometry") if isinstance(state.get("geometry"), dict) else {}
        payload["geometry"].update(
            {k: geometry.get(k) for k in payload["geometry"].keys() if k in geometry}
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
            "tile_order": list(DEFAULT_STATE["tile_order"]),
        }
