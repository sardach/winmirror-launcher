import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk

from .actions import WindowActions
from .persistence import (
    MAX_PANEL_HEIGHT,
    MAX_PANEL_WIDTH,
    MAX_TILE_HEIGHT,
    MAX_TILE_WIDTH,
    MIN_PANEL_HEIGHT,
    MIN_PANEL_WIDTH,
    MIN_TILE_HEIGHT,
    MIN_TILE_WIDTH,
    StateStore,
    clamp_int,
)
from .tile import MirrorTile


class LauncherPanelWindow:
    GRID_COLUMNS = 3

    def __init__(
        self,
        windows,
        fps,
        title,
        always_on_top,
        no_decorations,
        registry,
        layout_mode="horizontal",
        panel_mode="floating",
        anchor_edge="top",
        show_workspace_badge=True,
        show_title=False,
        show_close_button=False,
        hover_expand_enabled=True,
        refresh_mode="live",
        refresh_interval_ms=1000,
        tile_width=156,
        tile_height=96,
        panel_spacing=6,
        state_store=None,
        actions=None,
    ):
        self.actions = actions or WindowActions()
        self.registry = registry
        self.fps = fps
        self.layout_mode = layout_mode
        self.panel_mode = panel_mode
        self.anchor_edge = anchor_edge
        self.show_workspace_badge = show_workspace_badge
        self.show_title = show_title
        self.show_close_button = show_close_button
        self.hover_expand_enabled = hover_expand_enabled
        self.refresh_mode = refresh_mode
        self.refresh_interval_ms = int(refresh_interval_ms)
        self.tile_width = clamp_int(tile_width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, 120)
        self.tile_height = clamp_int(tile_height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, 78)
        self.panel_spacing = clamp_int(panel_spacing, 2, 16, 4)
        self.state_store = state_store or StateStore()
        self.state = self.state_store.load()
        self.tiles = []
        self.tile_by_id = {}
        self.tile_order = []
        self.pending_geometry = None
        self.save_timeout_id = None

        self.win = Gtk.Window()
        self.win.set_title(title or "winmirror-launcher panel")
        self.win.connect("destroy", self.on_window_destroy)
        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key_press)
        self.win.connect("configure-event", self.on_configure_event)
        self.win.set_keep_above(always_on_top)
        self.win.set_decorated(not no_decorations)
        self.apply_panel_mode(always_on_top, no_decorations)
        self.apply_saved_geometry()
        self.apply_geometry_limits()

        outer = Gtk.ScrolledWindow()
        if layout_mode == "vertical":
            outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        elif layout_mode == "grid":
            outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        else:
            outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.win.add(outer)

        self.container = self.build_container(layout_mode)
        outer.add(self.container)

        for window_info in windows:
            tile = self.create_tile(window_info)
            tile.connect("activate-requested", self.on_activate_requested)
            tile.connect("close-requested", self.on_close_requested)
            tile.connect("reorder-requested", self.on_reorder_requested)
            self.tiles.append(tile)
            self.tile_by_id[window_info.window_id] = tile
            if window_info.window_id not in self.tile_order:
                self.tile_order.append(window_info.window_id)

        self.rebuild_container()

        self.win.show_all()
        self.apply_fixed_position()
        GLib.timeout_add(1200, self.sync_panel_state)

    def create_tile(self, window_info):
        return MirrorTile(
            window_info,
            fps=self.fps,
            title_visible=self.show_title,
            show_close=self.show_close_button,
            show_workspace_badge=self.show_workspace_badge,
            hover_expand_enabled=self.hover_expand_enabled,
            refresh_mode=self.refresh_mode,
            refresh_interval_ms=self.refresh_interval_ms,
            tile_width=self.tile_width,
            tile_height=self.tile_height,
            panel_spacing=self.panel_spacing,
        )

    def apply_panel_mode(self, always_on_top, no_decorations):
        effective_top = always_on_top or self.panel_mode == "fixed"
        effective_undecorated = no_decorations or self.panel_mode == "fixed"
        self.win.set_keep_above(effective_top)
        self.win.set_decorated(not effective_undecorated)
        if self.panel_mode == "fixed":
            self.win.set_type_hint(Gdk.WindowTypeHint.DOCK)
        else:
            self.win.set_type_hint(Gdk.WindowTypeHint.NORMAL)

    def apply_saved_geometry(self):
        geometry = self.state.get("geometry", {})
        width = clamp_int(geometry.get("width"), MIN_PANEL_WIDTH, MAX_PANEL_WIDTH, 760)
        height = clamp_int(geometry.get("height"), MIN_PANEL_HEIGHT, MAX_PANEL_HEIGHT, 104)
        self.win.set_default_size(width, height)
        self.pending_geometry = {
            "x": geometry.get("x"),
            "y": geometry.get("y"),
            "width": width,
            "height": height,
        }

    def apply_geometry_limits(self):
        geometry = Gdk.Geometry()
        geometry.min_width = MIN_PANEL_WIDTH
        geometry.min_height = MIN_PANEL_HEIGHT
        geometry.max_width = MAX_PANEL_WIDTH
        geometry.max_height = MAX_PANEL_HEIGHT
        self.win.set_geometry_hints(
            None,
            geometry,
            Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.MAX_SIZE,
        )

    def apply_fixed_position(self):
        if self.panel_mode != "fixed":
            geometry = self.state.get("geometry", {})
            x = geometry.get("x")
            y = geometry.get("y")
            if x is not None and y is not None:
                self.win.move(int(x), int(y))
            return

        screen = Gdk.Screen.get_default()
        if screen is None:
            return

        width = screen.get_width()
        height = screen.get_height()
        current_width, current_height = self.win.get_size()
        x = 0
        y = 0

        if self.anchor_edge == "bottom":
            x = max(0, (width - current_width) // 2)
            y = max(0, height - current_height)
        elif self.anchor_edge == "left":
            x = 0
            y = max(0, (height - current_height) // 2)
        elif self.anchor_edge == "right":
            x = max(0, width - current_width)
            y = max(0, (height - current_height) // 2)
        else:
            x = max(0, (width - current_width) // 2)
            y = 0

        self.win.move(x, y)

    def build_container(self, layout_mode):
        if layout_mode == "grid":
            container = Gtk.Grid()
            container.set_row_spacing(self.panel_spacing)
            container.set_column_spacing(self.panel_spacing)
        else:
            orientation = (
                Gtk.Orientation.VERTICAL
                if layout_mode == "vertical"
                else Gtk.Orientation.HORIZONTAL
            )
            container = Gtk.Box(orientation=orientation, spacing=self.panel_spacing)

        margin = max(2, self.panel_spacing)
        container.set_margin_top(margin)
        container.set_margin_bottom(margin)
        container.set_margin_start(margin)
        container.set_margin_end(margin)
        return container

    def rebuild_container(self):
        for child in list(self.container.get_children()):
            self.container.remove(child)

        for index, window_id in enumerate(self.tile_order):
            tile = self.tile_by_id.get(window_id)
            if tile is None:
                continue
            if isinstance(self.container, Gtk.Grid):
                row = index // self.GRID_COLUMNS
                col = index % self.GRID_COLUMNS
                self.container.attach(tile, col, row, 1, 1)
            else:
                self.container.pack_start(tile, False, False, 0)

        self.container.show_all()
        self.save_state()

    def on_activate_requested(self, _tile, window_info):
        if self.actions.activate(window_info):
            for window_id, tile in self.tile_by_id.items():
                tile.set_active(window_id == window_info.window_id)

    def on_close_requested(self, tile, window_info):
        tile.stop_capture()
        if self.actions.close(window_info):
            tile.set_sensitive(False)

    def on_reorder_requested(self, _tile, source_id, target_id):
        self.reorder_tiles(source_id, target_id)

    def reorder_tiles(self, source_id, target_id):
        if source_id == target_id:
            return False
        if source_id not in self.tile_order or target_id not in self.tile_order:
            return False

        source_index = self.tile_order.index(source_id)
        target_index = self.tile_order.index(target_id)
        moved = self.tile_order.pop(source_index)
        self.tile_order.insert(target_index, moved)
        self.rebuild_container()
        return True

    def get_tile_order(self):
        return list(self.tile_order)

    def sync_panel_state(self):
        try:
            live_list = self.registry.list_windows()
            live_windows = {info.window_id: info for info in live_list}
            active_window_id = self.registry.get_active_window_id()
        except RuntimeError:
            return True

        live_ids = set(live_windows.keys())
        changed = False

        for window_id in list(self.tile_by_id.keys()):
            if window_id in live_ids:
                continue
            tile = self.tile_by_id.pop(window_id)
            tile.stop_capture("Ventana cerrada")
            self.tiles = [item for item in self.tiles if item is not tile]
            if window_id in self.tile_order:
                self.tile_order.remove(window_id)
            self.container.remove(tile)
            changed = True

        known_ids = set(self.tile_by_id.keys())
        for info in live_list:
            if info.window_id in known_ids:
                continue
            tile = self.create_tile(info)
            tile.connect("activate-requested", self.on_activate_requested)
            tile.connect("close-requested", self.on_close_requested)
            tile.connect("reorder-requested", self.on_reorder_requested)
            self.tiles.append(tile)
            self.tile_by_id[info.window_id] = tile
            if info.window_id not in self.tile_order:
                self.tile_order.append(info.window_id)
            changed = True

        if changed:
            self.rebuild_container()

        for window_id, tile in list(self.tile_by_id.items()):
            window_info = live_windows.get(window_id)
            if window_info is None:
                continue

            tile.update_window_info(window_info)
            tile.set_active(window_id == active_window_id)

        return True

    def save_state(self):
        geometry = self.pending_geometry or {}
        x = geometry.get("x")
        y = geometry.get("y")
        width = int(geometry.get("width") or self.win.get_size()[0])
        height = int(geometry.get("height") or self.win.get_size()[1])
        self.state.update(
            {
                "state_version": 2,
                "layout_mode": self.layout_mode,
                "panel_mode": self.panel_mode,
                "anchor_edge": self.anchor_edge,
                "show_workspace_badge": self.show_workspace_badge,
                "show_title": self.show_title,
                "show_close_button": self.show_close_button,
                "hover_expand_enabled": self.hover_expand_enabled,
                "refresh_mode": self.refresh_mode,
                "refresh_interval_ms": self.refresh_interval_ms,
                "tile_width": self.tile_width,
                "tile_height": self.tile_height,
                "panel_spacing": self.panel_spacing,
                "tile_order": self.get_tile_order(),
                "geometry": {
                    "x": None if x is None else int(x),
                    "y": None if y is None else int(y),
                    "width": width,
                    "height": height,
                },
            }
        )
        self.state_store.save(self.state)

    def flush_deferred_save(self):
        self.save_timeout_id = None
        self.save_state()
        if self.panel_mode == "fixed":
            GLib.idle_add(self.apply_fixed_position)
        return False

    def on_configure_event(self, _win, event):
        self.pending_geometry = {
            "x": event.x,
            "y": event.y,
            "width": event.width,
            "height": event.height,
        }
        if self.save_timeout_id is not None:
            GLib.source_remove(self.save_timeout_id)
        self.save_timeout_id = GLib.timeout_add(180, self.flush_deferred_save)
        if self.panel_mode == "fixed":
            GLib.idle_add(self.apply_fixed_position)
        return False

    def on_destroy(self, *_args):
        if self.save_timeout_id is not None:
            GLib.source_remove(self.save_timeout_id)
            self.save_timeout_id = None
        self.save_state()

    def on_window_destroy(self, *_args):
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def apply_settings(self, settings):
        self.layout_mode = settings.get("layout_mode", self.layout_mode)
        self.panel_mode = settings.get("panel_mode", self.panel_mode)
        self.anchor_edge = settings.get("anchor_edge", self.anchor_edge)
        self.show_workspace_badge = bool(
            settings.get("show_workspace_badge", self.show_workspace_badge)
        )
        self.show_title = bool(settings.get("show_title", self.show_title))
        self.show_close_button = bool(
            settings.get("show_close_button", self.show_close_button)
        )
        self.hover_expand_enabled = bool(
            settings.get("hover_expand_enabled", self.hover_expand_enabled)
        )
        self.refresh_mode = settings.get("refresh_mode", self.refresh_mode)
        self.refresh_interval_ms = int(
            settings.get("refresh_interval_ms", self.refresh_interval_ms)
        )
        self.tile_width = int(settings.get("tile_width", self.tile_width))
        self.tile_height = int(settings.get("tile_height", self.tile_height))
        self.panel_spacing = int(settings.get("panel_spacing", self.panel_spacing))
        self.tile_width = clamp_int(self.tile_width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, 120)
        self.tile_height = clamp_int(self.tile_height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, 78)
        self.panel_spacing = clamp_int(self.panel_spacing, 2, 16, 4)

        parent = self.container.get_parent()
        if parent is not None:
            parent.remove(self.container)
        self.container = self.build_container(self.layout_mode)
        parent.add(self.container)

        live_windows = []
        for window_id in self.tile_order:
            tile = self.tile_by_id.get(window_id)
            if tile is not None:
                live_windows.append(tile.window_info)

        self.tiles = []
        self.tile_by_id = {}
        for info in live_windows:
            tile = self.create_tile(info)
            tile.connect("activate-requested", self.on_activate_requested)
            tile.connect("close-requested", self.on_close_requested)
            tile.connect("reorder-requested", self.on_reorder_requested)
            self.tiles.append(tile)
            self.tile_by_id[info.window_id] = tile

        self.apply_panel_mode(False, False)
        self.rebuild_container()
        self.apply_fixed_position()
        self.win.show_all()

    def open_config_window(self):
        from .settings import SettingsWindow

        SettingsWindow(self)

    def on_key_press(self, _win, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "comma" and (event.state & Gdk.ModifierType.CONTROL_MASK):
            self.open_config_window()
            return True
        if key == "Escape":
            Gtk.main_quit()
            return True
        if key in ("q", "Q") and (event.state & Gdk.ModifierType.CONTROL_MASK):
            Gtk.main_quit()
            return True
        return False
