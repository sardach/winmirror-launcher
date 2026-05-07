import gi
import math

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gdk, GdkX11, GLib, Gtk, Pango, PangoCairo

from .window_registry import WindowRegistry
from .x11 import run_command


MIN_TILE_WIDTH = 24
MAX_TILE_WIDTH = 960
MIN_TILE_HEIGHT = 18
MAX_TILE_HEIGHT = 640
SHRINK_TILE_WIDTH = 1
SHRINK_TILE_HEIGHT = 1
DEFAULT_TILE_WIDTH = 120
DEFAULT_TILE_HEIGHT = 72
WINDOW_REFRESH_MS = 1800
ACTIVE_WINDOW_POLL_MS = 500
ORDER_MODES = {"manual", "name", "last-used"}
LABEL_MODES = {"title", "app"}
IDLE_MODES = {"off", "collapse", "hide"}
HOVER_MODES = {
    "off": 1.0,
    "soft": 1.08,
    "medium": 1.18,
    "large": 1.32,
}
MIN_HOVER_SCALE = 1.0
MAX_HOVER_SCALE = 2.5


def clamp(value, lower, upper, fallback):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(lower, min(upper, value))


def refresh_interval_ms(fps):
    try:
        fps = float(fps)
    except (TypeError, ValueError):
        fps = 1.0
    if fps <= 0:
        return None
    return max(100, int(round(1000.0 / fps)))


def interval_seconds_to_ms(seconds):
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return max(100, int(round(seconds * 1000.0)))


def normalize_hover_mode(mode, hover_expand=False):
    if mode in HOVER_MODES:
        return mode
    return "medium" if hover_expand else "off"


def normalize_hover_scale(value, mode=None, hover_expand=False):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = HOVER_MODES[normalize_hover_mode(mode, hover_expand)]
    return max(MIN_HOVER_SCALE, min(MAX_HOVER_SCALE, value))


def normalize_order_mode(value):
    return value if value in ORDER_MODES else "last-used"


def normalize_label_mode(value):
    return value if value in LABEL_MODES else "title"


def normalize_idle_mode(value):
    return value if value in IDLE_MODES else "off"


def app_name_from_wm_class(wm_class):
    value = (wm_class or "").strip()
    if not value:
        return "app"
    return value.split(".")[-1] or value


class SimpleMirrorTile(Gtk.DrawingArea):
    def __init__(
        self,
        window_info,
        width=DEFAULT_TILE_WIDTH,
        height=DEFAULT_TILE_HEIGHT,
        fps=1.0,
        frame_interval_seconds=None,
        show_title=False,
        show_close=False,
        show_workspace=False,
        hover_expand=False,
        hover_mode=None,
        hover_scale=None,
        show_borders=False,
        label_mode="title",
        panel=None,
    ):
        super().__init__()
        self.panel = panel
        self.window_info = window_info
        self.tile_width = clamp(width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        self.hover_mode = normalize_hover_mode(hover_mode, hover_expand)
        self.hover_scale = normalize_hover_scale(hover_scale, self.hover_mode, hover_expand)
        self.interval_ms = interval_seconds_to_ms(frame_interval_seconds) or refresh_interval_ms(fps)
        self.source_window = None
        self.current_pixbuf = None
        self.status = ""
        self.show_title = bool(show_title)
        self.show_close = bool(show_close)
        self.show_workspace = bool(show_workspace)
        self.hover_expand = self.hover_mode != "off"
        self.show_borders = bool(show_borders)
        self.label_mode = normalize_label_mode(label_mode)
        self.hovered = False
        self.dragging = False
        self.refresh_source_id = None
        self.layout_width = self.tile_width
        self.layout_height = self.tile_height

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_layout_size(self.layout_width, self.layout_height)
        self.set_tooltip_text(window_info.title)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("destroy", self.on_destroy)

        self.attach_source()
        self.set_refresh_interval(self.interval_ms)
        self.refresh()

    def on_destroy(self, *_args):
        if self.refresh_source_id is not None:
            GLib.source_remove(self.refresh_source_id)
            self.refresh_source_id = None

    def set_fps(self, fps):
        self.set_refresh_interval(refresh_interval_ms(fps))

    def set_frame_interval_seconds(self, seconds):
        self.set_refresh_interval(interval_seconds_to_ms(seconds))

    def set_refresh_interval(self, interval_ms):
        self.interval_ms = interval_ms
        if self.refresh_source_id is not None:
            GLib.source_remove(self.refresh_source_id)
            self.refresh_source_id = None
        if self.interval_ms is not None:
            self.refresh_source_id = GLib.timeout_add(self.interval_ms, self.refresh)

    def set_dimensions(self, width, height):
        self.tile_width = clamp(width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        if self.panel is None:
            self.set_layout_size(self.tile_width, self.tile_height)
        self.queue_resize()
        self.queue_draw()

    def set_layout_size(self, width, height):
        self.layout_width = max(1, int(round(width)))
        self.layout_height = max(1, int(round(height)))
        self.set_size_request(self.layout_width, self.layout_height)

    def release_layout_size(self):
        self.layout_width = SHRINK_TILE_WIDTH
        self.layout_height = SHRINK_TILE_HEIGHT
        self.set_size_request(SHRINK_TILE_WIDTH, SHRINK_TILE_HEIGHT)

    def set_display_options(
        self,
        show_title=None,
        show_close=None,
        show_workspace=None,
        hover_expand=None,
        hover_mode=None,
        hover_scale=None,
        show_borders=None,
        label_mode=None,
    ):
        if show_title is not None:
            self.show_title = bool(show_title)
        if show_close is not None:
            self.show_close = bool(show_close)
        if show_workspace is not None:
            self.show_workspace = bool(show_workspace)
        if hover_mode is not None or hover_expand is not None:
            self.hover_mode = normalize_hover_mode(hover_mode, hover_expand if hover_expand is not None else self.hover_expand)
            self.hover_expand = self.hover_mode != "off"
            if hover_scale is None:
                self.hover_scale = normalize_hover_scale(None, self.hover_mode, self.hover_expand)
        if hover_scale is not None:
            self.hover_scale = normalize_hover_scale(hover_scale, self.hover_mode, self.hover_expand)
            self.hover_expand = self.hover_scale > 1.0
            if self.hover_scale <= 1.0:
                self.hover_mode = "off"
        if show_borders is not None:
            self.show_borders = bool(show_borders)
        if label_mode is not None:
            self.label_mode = normalize_label_mode(label_mode)
        self.set_dimensions(self.tile_width, self.tile_height)

    def display_name(self):
        if self.label_mode == "app":
            return app_name_from_wm_class(self.window_info.wm_class)
        return self.window_info.title or app_name_from_wm_class(self.window_info.wm_class)

    def attach_source(self):
        display = Gdk.Display.get_default()
        if display is None:
            self.status = "sin display"
            return False
        try:
            self.source_window = GdkX11.X11Window.foreign_new_for_display(
                display,
                int(self.window_info.window_id),
            )
        except (TypeError, ValueError):
            self.source_window = None
        if self.source_window is None:
            self.status = "cerrada"
            return False
        return True

    def is_viewable(self):
        proc = run_command(["xwininfo", "-id", str(int(self.window_info.window_id))])
        if proc is None or proc.returncode != 0:
            self.status = "cerrada"
            return False
        if "Map State: IsViewable" not in proc.stdout:
            self.status = "oculta"
            return False
        return True

    def refresh(self):
        if self.source_window is None and not self.attach_source():
            self.current_pixbuf = None
            self.queue_draw()
            return True

        if not self.is_viewable():
            self.current_pixbuf = None
            self.queue_draw()
            return True

        width = max(1, self.source_window.get_width())
        height = max(1, self.source_window.get_height())
        if width <= 1 or height <= 1:
            self.status = "sin imagen"
            self.current_pixbuf = None
            self.queue_draw()
            return True

        Gdk.error_trap_push()
        pixbuf = Gdk.pixbuf_get_from_window(self.source_window, 0, 0, width, height)
        Gdk.flush()
        error = Gdk.error_trap_pop()
        if error:
            self.status = "sin imagen"
            self.current_pixbuf = None
            self.source_window = None
            self.queue_draw()
            return True
        if pixbuf is None:
            self.status = "sin imagen"
            self.current_pixbuf = None
        else:
            self.status = ""
            self.current_pixbuf = pixbuf
        self.queue_draw()
        return True

    def activate_window(self):
        window_id = str(int(self.window_info.window_id))
        proc = run_command(["xdotool", "windowactivate", "--sync", window_id])
        if proc is not None and proc.returncode == 0:
            if self.panel is not None:
                self.panel.note_window_used(self.window_info.window_id)
            return True
        proc = run_command(["wmctrl", "-ia", self.window_info.window_hex])
        activated = proc is not None and proc.returncode == 0
        if activated and self.panel is not None:
            self.panel.note_window_used(self.window_info.window_id)
        return activated

    def close_window(self):
        proc = run_command(["wmctrl", "-ic", self.window_info.window_hex])
        return proc is not None and proc.returncode == 0

    def on_button_press(self, _widget, event):
        if int(event.button) == 3 and self.panel is not None:
            self.panel.show_context_menu(event, self)
            return True
        if self.panel is not None and self.panel.order_edit_mode and int(event.button) == 1:
            if self.handle_order_edit_click(event):
                return True
        alloc = self.get_allocation()
        if self.show_close and int(event.button) == 1:
            if event.x >= alloc.width - 18 and event.y <= 18:
                self.close_window()
                return True
        if int(event.button) == 1:
            self.activate_window()
            return True
        if int(event.button) == 2:
            self.close_window()
            return True
        return False

    def handle_order_edit_click(self, event):
        alloc = self.get_allocation()
        width = max(1, alloc.width)
        height = max(1, alloc.height)
        control_size = max(16, min(28, min(width, height) // 3))
        if event.y <= control_size:
            if event.x <= control_size:
                self.panel.move_tile(self, -1)
                return True
            if event.x >= width - control_size:
                self.panel.move_tile(self, 1)
                return True
        if event.y >= height - control_size:
            if event.x <= control_size:
                self.panel.move_tile(self, -self.panel.current_columns)
                return True
            if event.x >= width - control_size:
                self.panel.move_tile(self, self.panel.current_columns)
                return True
        return False

    def on_enter(self, *_args):
        self.hovered = True
        if self.panel is not None:
            self.panel.note_pointer_inside(True)
            self.panel.set_hovered_tile(self)
        self.queue_draw()
        return False

    def on_leave(self, *_args):
        self.hovered = False
        if self.panel is not None:
            self.panel.set_hovered_tile(None)
            self.panel.note_pointer_inside(False)
        self.queue_draw()
        return False

    def on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        width = max(1, alloc.width)
        height = max(1, alloc.height)

        cr.set_source_rgb(0.02, 0.02, 0.02)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if self.current_pixbuf is None:
            self.draw_placeholder(widget, cr, width, height)
            if self.show_borders:
                self.draw_border(cr, width, height)
            return False

        src_w = self.current_pixbuf.get_width()
        src_h = self.current_pixbuf.get_height()
        scale = min(float(width) / src_w, float(height) / src_h)
        draw_w = src_w * scale
        draw_h = src_h * scale
        off_x = (width - draw_w) / 2.0
        off_y = (height - draw_h) / 2.0

        cr.save()
        cr.translate(off_x, off_y)
        cr.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cr, self.current_pixbuf, 0, 0)
        cr.paint()
        cr.restore()

        if self.hovered and self.hover_scale > 1.0:
            cr.set_source_rgba(1.0, 1.0, 1.0, min(0.18, 0.04 + ((self.hover_scale - 1.0) * 0.08)))
            cr.rectangle(0, 0, width, height)
            cr.fill()
        if self.show_borders:
            self.draw_border(cr, width, height)
        self.draw_overlays(widget, cr, width, height)
        return False

    def draw_border(self, cr, width, height):
        cr.set_source_rgb(0.18, 0.18, 0.18)
        cr.set_line_width(1.0)
        cr.rectangle(0.5, 0.5, max(0, width - 1), max(0, height - 1))
        cr.stroke()

    def draw_overlays(self, widget, cr, width, height):
        if self.show_workspace:
            self.draw_badge(widget, cr, 3, 2, f"{self.window_info.desktop_index}")

        if self.show_close:
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.65)
            cr.rectangle(width - 18, 0, 18, 18)
            cr.fill()
            layout = widget.create_pango_layout("x")
            layout.set_font_description(Pango.FontDescription("Sans Bold 8"))
            tw, th = layout.get_pixel_size()
            cr.set_source_rgb(0.95, 0.95, 0.95)
            cr.move_to(width - 9 - tw / 2.0, 9 - th / 2.0)
            PangoCairo.show_layout(cr, layout)

        if self.show_title:
            title = self.display_name()[:42]
            layout = widget.create_pango_layout(title)
            layout.set_font_description(Pango.FontDescription("Sans 8"))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            layout.set_width(max(1, width - 8) * Pango.SCALE)
            _tw, th = layout.get_pixel_size()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.68)
            cr.rectangle(0, max(0, height - th - 5), width, th + 5)
            cr.fill()
            cr.set_source_rgb(0.92, 0.92, 0.92)
            cr.move_to(4, max(1, height - th - 3))
            PangoCairo.show_layout(cr, layout)

        if self.panel is not None and self.panel.order_edit_mode:
            self.draw_order_controls(widget, cr, width, height)

    def draw_order_controls(self, widget, cr, width, height):
        control_size = max(16, min(28, min(width, height) // 3))
        if width < 24 or height < 18:
            return

        cr.set_source_rgba(0.0, 0.0, 0.0, 0.72)
        for x, y in (
            (0, 0),
            (width - control_size, 0),
            (0, height - control_size),
            (width - control_size, height - control_size),
        ):
            cr.rectangle(x, y, control_size, control_size)
            cr.fill()

        arrows = (
            ("<", 0, 0),
            (">", width - control_size, 0),
            ("^", 0, height - control_size),
            ("v", width - control_size, height - control_size),
        )
        cr.set_source_rgb(0.95, 0.95, 0.95)
        for text, x, y in arrows:
            layout = widget.create_pango_layout(text)
            layout.set_font_description(Pango.FontDescription("Sans Bold 8"))
            tw, th = layout.get_pixel_size()
            cr.move_to(x + (control_size - tw) / 2.0, y + (control_size - th) / 2.0)
            PangoCairo.show_layout(cr, layout)

    def draw_badge(self, widget, cr, x, y, text):
        layout = widget.create_pango_layout(text)
        layout.set_font_description(Pango.FontDescription("Sans Bold 8"))
        tw, th = layout.get_pixel_size()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.68)
        cr.rectangle(x, y, tw + 8, th + 4)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.move_to(x + 4, y + 2)
        PangoCairo.show_layout(cr, layout)

    def draw_placeholder(self, widget, cr, width, height):
        title = self.display_name() or self.window_info.window_hex
        layout = widget.create_pango_layout(title)
        layout.set_font_description(Pango.FontDescription("Sans Bold 8"))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        layout.set_width(max(1, width - 10) * Pango.SCALE)
        tw, th = layout.get_pixel_size()
        cr.set_source_rgb(0.82, 0.82, 0.82)
        cr.move_to(5, max(4, (height - th) / 2.0 - 5))
        PangoCairo.show_layout(cr, layout)

        if self.status:
            status_layout = widget.create_pango_layout(self.status)
            status_layout.set_font_description(Pango.FontDescription("Sans 7"))
            sw, sh = status_layout.get_pixel_size()
            cr.set_source_rgb(0.55, 0.55, 0.55)
            cr.move_to(max(5, (width - sw) / 2.0), min(height - sh - 3, (height + th) / 2.0 + 1))
            PangoCairo.show_layout(cr, status_layout)


class SimpleLauncherPanel:
    def __init__(
        self,
        windows,
        tile_width=DEFAULT_TILE_WIDTH,
        tile_height=DEFAULT_TILE_HEIGHT,
        fps=1.0,
        title=None,
        show_title=False,
        show_close=False,
        show_workspace=False,
        hover_expand=False,
        hover_mode=None,
        hover_scale=None,
        show_borders=False,
        order_mode="last-used",
        label_mode="title",
        sticky_workspaces=False,
        idle_mode="off",
        idle_delay_ms=700,
        frame_interval_seconds=None,
        excluded_window_ids=None,
        registry=None,
    ):
        self.registry = registry or WindowRegistry()
        self.excluded_window_ids = {int(item) for item in (excluded_window_ids or [])}
        self.own_window_id = None
        self.windows = windows
        self.tile_width = clamp(tile_width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(tile_height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        self.fps = fps
        self.show_title = bool(show_title)
        self.show_close = bool(show_close)
        self.show_workspace = bool(show_workspace)
        self.hover_mode = normalize_hover_mode(hover_mode, hover_expand)
        self.hover_expand = self.hover_mode != "off"
        self.hover_scale = normalize_hover_scale(hover_scale, self.hover_mode, hover_expand)
        self.show_borders = bool(show_borders)
        self.label_mode = normalize_label_mode(label_mode)
        self.sticky_workspaces = bool(sticky_workspaces)
        self.idle_mode = normalize_idle_mode(idle_mode)
        self.idle_delay_ms = clamp(idle_delay_ms, 100, 5000, 700)
        self.frame_interval_seconds = frame_interval_seconds
        self.window_refresh_source_id = None
        self.active_window_source_id = None
        self.idle_source_id = None
        self.hidden_poll_source_id = None
        self.current_columns = 0
        self.current_rows = 0
        self.order_edit_mode = False
        self.order_mode = normalize_order_mode(order_mode)
        self.mru_window_ids = []
        self.hovered_tile = None
        self.pointer_inside_panel = False
        self.collapsed = False
        self.hidden_by_idle = False
        self.restore_size = None
        self.restore_rect = None

        self.win = Gtk.Window()
        self.win.set_title(title or "winmirror-launcher")
        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key_press)
        self.win.set_resizable(True)
        self.win.set_decorated(True)
        self.win.connect("configure-event", self.on_configure_event)
        self.win.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.win.connect("button-press-event", self.on_panel_button_press)
        self.win.connect("enter-notify-event", self.on_panel_enter)
        self.win.connect("leave-notify-event", self.on_panel_leave)

        target_width = max(240, min(len(windows) * self.tile_width, 980))
        target_height = max(48, self.tile_height)
        self.win.set_default_size(target_width, target_height)

        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(0)
        self.grid.set_column_spacing(0)
        self.grid.set_hexpand(True)
        self.grid.set_vexpand(True)
        self.grid.set_row_homogeneous(False)
        self.grid.set_column_homogeneous(False)
        self.win.add(self.grid)

        self.tiles = []
        for info in self.filter_windows(windows):
            self.add_tile(info)

        self.win.show_all()
        self.capture_own_window_id()
        self.apply_workspace_behavior()
        self.note_window_used(self.registry.get_active_window_id(), apply_order=False)
        self.apply_order()
        self.fit_tiles_to_window()
        self.window_refresh_source_id = GLib.timeout_add(WINDOW_REFRESH_MS, self.reconcile_windows)
        self.active_window_source_id = GLib.timeout_add(ACTIVE_WINDOW_POLL_MS, self.poll_active_window)

    def capture_own_window_id(self):
        gdk_window = self.win.get_window()
        if gdk_window is None:
            return
        try:
            self.own_window_id = int(gdk_window.get_xid())
        except AttributeError:
            self.own_window_id = None

    def apply_workspace_behavior(self):
        if not self.sticky_workspaces or self.own_window_id is None:
            return
        run_command(["wmctrl", "-i", "-r", f"0x{self.own_window_id:x}", "-b", "add,sticky"])

    def filter_windows(self, windows):
        filtered = []
        for info in windows:
            if int(info.window_id) in self.excluded_window_ids:
                continue
            if self.own_window_id is not None and int(info.window_id) == self.own_window_id:
                continue
            filtered.append(info)
        return filtered

    def add_tile(self, info):
        tile = SimpleMirrorTile(
            info,
            width=self.tile_width,
            height=self.tile_height,
            fps=self.fps,
            frame_interval_seconds=self.frame_interval_seconds,
            show_title=self.show_title,
            show_close=self.show_close,
            show_workspace=self.show_workspace,
            hover_mode=self.hover_mode,
            hover_scale=self.hover_scale,
            show_borders=self.show_borders,
            label_mode=self.label_mode,
            panel=self,
        )
        self.tiles.append(tile)
        self.grid.attach(tile, len(self.tiles) - 1, 0, 1, 1)
        self.current_columns = 0
        self.current_rows = 0
        tile.show_all()
        return tile

    def tile_ids(self):
        return [tile.window_info.window_id for tile in self.tiles]

    def remove_tile(self, tile):
        if tile in self.tiles:
            self.tiles.remove(tile)
        self.grid.remove(tile)
        self.current_columns = 0
        self.current_rows = 0
        if self.hovered_tile is tile:
            self.hovered_tile = None
        tile.destroy()

    def reconcile_windows(self):
        try:
            windows = self.filter_windows(self.registry.list_windows())
        except RuntimeError:
            return True

        before_ids = [tile.window_info.window_id for tile in self.tiles]
        next_by_id = {info.window_id: info for info in windows}
        existing_by_id = {tile.window_info.window_id: tile for tile in self.tiles}

        for tile in list(self.tiles):
            if tile.window_info.window_id not in next_by_id:
                self.remove_tile(tile)

        for info in windows:
            tile = existing_by_id.get(info.window_id)
            if tile is None:
                self.add_tile(info)
            else:
                tile.window_info = info
                tile.set_tooltip_text(info.title)

        self.apply_order()
        after_ids = [tile.window_info.window_id for tile in self.tiles]
        if before_ids != after_ids:
            self.fit_tiles_to_window()
        return True

    def poll_active_window(self):
        self.note_window_used(self.registry.get_active_window_id())
        return True

    def note_window_used(self, window_id, apply_order=True):
        if window_id is None:
            return
        window_id = int(window_id)
        if self.own_window_id is not None and window_id == self.own_window_id:
            return
        if window_id not in {tile.window_info.window_id for tile in self.tiles}:
            return
        if window_id in self.mru_window_ids:
            self.mru_window_ids.remove(window_id)
        self.mru_window_ids.insert(0, window_id)
        if apply_order and self.order_mode == "last-used":
            self.apply_order()

    def apply_order(self):
        if len(self.tiles) < 2:
            return
        before_ids = self.tile_ids()
        if self.order_mode == "name":
            self.tiles.sort(key=self.window_sort_key)
        elif self.order_mode == "last-used":
            mru_rank = {window_id: index for index, window_id in enumerate(self.mru_window_ids)}
            fallback_rank = {window_id: index for index, window_id in enumerate(before_ids)}
            self.tiles.sort(
                key=lambda tile: (
                    mru_rank.get(tile.window_info.window_id, len(self.tiles) + fallback_rank[tile.window_info.window_id]),
                    self.window_sort_key(tile),
                )
            )
        if self.tile_ids() != before_ids:
            self.current_columns = 0
            self.current_rows = 0
            self.fit_tiles_to_window()

    def window_sort_key(self, tile):
        info = tile.window_info
        title = (info.title or "").casefold()
        wm_class = (info.wm_class or "").casefold()
        return (title, wm_class, int(info.window_id))

    def choose_grid_shape(self, width, height, count):
        if count <= 1:
            return 1, 1
        width = max(1, int(width))
        height = max(1, int(height))
        best = None
        for columns in range(1, count + 1):
            rows = int(math.ceil(float(count) / columns))
            tile_width = max(1, width // columns)
            tile_height = max(1, height // rows)
            visible_area = min(tile_width, MAX_TILE_WIDTH) * min(tile_height, MAX_TILE_HEIGHT)
            aspect = float(tile_width) / max(1.0, float(tile_height))
            aspect_penalty = abs(math.log(max(0.1, aspect / 1.6)))
            empty_slots = (columns * rows) - count
            score = visible_area - (visible_area * aspect_penalty * 0.18) - (empty_slots * 40)
            if best is None or score > best[0]:
                best = (score, columns, rows)
        return best[1], best[2]

    def relayout_tiles(self, columns, rows):
        columns = max(1, int(columns))
        rows = max(1, int(rows))
        if columns == self.current_columns and rows == self.current_rows:
            return
        self.current_columns = columns
        self.current_rows = rows
        for tile in self.tiles:
            self.grid.remove(tile)
        for index, tile in enumerate(self.tiles):
            self.grid.attach(tile, index % columns, index // columns, 1, 1)
        self.grid.show_all()

    def fit_tiles_to_window(self):
        if not self.tiles:
            return
        alloc = self.win.get_allocation()
        width = alloc.width
        height = alloc.height
        if width <= 1 or height <= 1:
            return
        columns, rows = self.choose_grid_shape(width, height, len(self.tiles))
        self.relayout_tiles(columns, rows)
        target_width = clamp(width // columns, MIN_TILE_WIDTH, MAX_TILE_WIDTH, self.tile_width)
        target_height = clamp(height // rows, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, self.tile_height)
        self.tile_width = target_width
        self.tile_height = target_height
        for tile in self.tiles:
            tile.set_dimensions(self.tile_width, self.tile_height)
        self.apply_tile_size_requests()

    def set_hovered_tile(self, tile):
        next_tile = tile if tile in self.tiles and self.hover_expand and self.hover_scale > 1.0 else None
        if self.hovered_tile is next_tile:
            return
        self.hovered_tile = next_tile
        self.apply_tile_size_requests()

    def on_panel_enter(self, *_args):
        self.note_pointer_inside(True)
        return False

    def on_panel_leave(self, *_args):
        self.note_pointer_inside(False)
        return False

    def note_pointer_inside(self, inside):
        self.pointer_inside_panel = bool(inside)
        if self.pointer_inside_panel:
            self.restore_from_idle()
            return
        self.schedule_idle_mode()

    def schedule_idle_mode(self):
        if self.idle_mode == "off":
            return
        if self.idle_source_id is not None:
            GLib.source_remove(self.idle_source_id)
        self.idle_source_id = GLib.timeout_add(self.idle_delay_ms, self.apply_idle_mode)

    def apply_idle_mode(self):
        self.idle_source_id = None
        if self.pointer_inside_panel or self.idle_mode == "off":
            return False
        if self.idle_mode == "collapse":
            self.collapse_for_idle()
        elif self.idle_mode == "hide":
            self.hide_for_idle()
        return False

    def collapse_for_idle(self):
        if self.collapsed:
            return
        self.restore_size = self.win.get_size()
        for tile in self.tiles:
            tile.release_layout_size()
        self.collapsed = True
        width = max(80, self.restore_size[0]) if self.restore_size else 240
        self.win.resize(width, 10)

    def hide_for_idle(self):
        if self.hidden_by_idle:
            return
        x, y = self.win.get_position()
        width, height = self.win.get_size()
        self.restore_rect = (x, y, max(1, width), max(1, height))
        self.hidden_by_idle = True
        self.win.hide()
        if self.hidden_poll_source_id is None:
            self.hidden_poll_source_id = GLib.timeout_add(160, self.poll_hidden_restore)

    def poll_hidden_restore(self):
        if not self.hidden_by_idle:
            self.hidden_poll_source_id = None
            return False
        if self.restore_rect is None:
            return True
        pointer = self.get_pointer_position()
        if pointer is None:
            return True
        x, y, width, height = self.restore_rect
        px, py = pointer
        if x <= px <= x + width and y <= py <= y + height:
            self.restore_from_idle()
            self.hidden_poll_source_id = None
            return False
        return True

    def get_pointer_position(self):
        display = Gdk.Display.get_default()
        if display is None:
            return None
        seat = display.get_default_seat()
        if seat is None:
            return None
        pointer = seat.get_pointer()
        if pointer is None:
            return None
        _screen, x, y = pointer.get_position()
        return x, y

    def restore_from_idle(self):
        if self.idle_source_id is not None:
            GLib.source_remove(self.idle_source_id)
            self.idle_source_id = None
        if self.hidden_by_idle:
            self.hidden_by_idle = False
            if self.restore_rect is not None:
                x, y, width, height = self.restore_rect
                self.win.move(x, y)
                self.win.resize(width, height)
            self.win.show_all()
        if self.collapsed:
            self.collapsed = False
            if self.restore_size is not None:
                self.win.resize(max(1, self.restore_size[0]), max(1, self.restore_size[1]))
        self.fit_tiles_to_window()

    def apply_tile_size_requests(self):
        if not self.tiles:
            return
        columns = max(1, self.current_columns or len(self.tiles))
        alloc = self.win.get_allocation()
        total_width = max(1, alloc.width)

        if self.hovered_tile not in self.tiles or self.hover_scale <= 1.0:
            for tile in self.tiles:
                tile.release_layout_size()
            self.grid.queue_resize()
            return

        column_weights = [1.0 for _index in range(columns)]
        hover_index = self.tiles.index(self.hovered_tile)
        hover_column = hover_index % columns
        column_weights[hover_column] = self.hover_scale
        column_widths = self.distribute_pixels(total_width, column_weights)

        for index, tile in enumerate(self.tiles):
            if index % columns == hover_column:
                tile.set_layout_size(column_widths[hover_column], SHRINK_TILE_HEIGHT)
            else:
                tile.release_layout_size()
        self.grid.queue_resize()

    def distribute_pixels(self, total, weights):
        total = max(1, int(total))
        weight_sum = max(0.001, sum(weights))
        raw_sizes = [float(total) * (weight / weight_sum) for weight in weights]
        sizes = [max(1, int(math.floor(size))) for size in raw_sizes]
        remainder = total - sum(sizes)
        fractions = sorted(
            range(len(raw_sizes)),
            key=lambda index: raw_sizes[index] - math.floor(raw_sizes[index]),
            reverse=True,
        )
        step = 1 if remainder >= 0 else -1
        for index in fractions:
            if remainder == 0:
                break
            if step < 0 and sizes[index] <= 1:
                continue
            sizes[index] += step
            remainder -= step
        return sizes

    def on_panel_button_press(self, _widget, event):
        if int(event.button) == 3:
            self.show_context_menu(event, None)
            return True
        return False

    def show_context_menu(self, event, tile):
        menu = Gtk.Menu()

        self.add_check_item(menu, "Mostrar nombre", self.show_title, lambda active: self.update_options(show_title=active))
        self.add_check_item(menu, "Mostrar cerrar", self.show_close, lambda active: self.update_options(show_close=active))
        self.add_check_item(menu, "Mostrar workspace", self.show_workspace, lambda active: self.update_options(show_workspace=active))
        self.add_check_item(menu, "Mostrar bordes", self.show_borders, lambda active: self.update_options(show_borders=active))
        self.add_check_item(menu, "Editar orden", self.order_edit_mode, self.set_order_edit_mode)
        menu.append(Gtk.SeparatorMenuItem())

        order_menu = Gtk.Menu()
        for label, mode in (("Ultima app usada", "last-used"), ("Nombre", "name"), ("Manual", "manual")):
            item = Gtk.RadioMenuItem.new_with_label_from_widget(
                order_menu.get_children()[0] if order_menu.get_children() else None,
                label,
            )
            item.set_active(self.order_mode == mode)
            item.connect("toggled", lambda check, value=mode: check.get_active() and self.set_order_mode(value))
            order_menu.append(item)
        order_item = Gtk.MenuItem(label="Orden")
        order_item.set_submenu(order_menu)
        menu.append(order_item)

        hover_menu = Gtk.Menu()
        for label, mode in (("Sin agrandar", "off"), ("Suave", "soft"), ("Medio", "medium"), ("Grande", "large")):
            item = Gtk.RadioMenuItem.new_with_label_from_widget(
                hover_menu.get_children()[0] if hover_menu.get_children() else None,
                label,
            )
            item.set_active(self.hover_mode == mode)
            item.connect("toggled", lambda check, value=mode: check.get_active() and self.update_options(hover_mode=value))
            hover_menu.append(item)
        hover_menu.append(Gtk.SeparatorMenuItem())
        reduce_item = Gtk.MenuItem(label="Disminuir efecto")
        reduce_item.connect("activate", lambda *_args: self.adjust_hover_scale(-0.1))
        hover_menu.append(reduce_item)
        increase_item = Gtk.MenuItem(label="Aumentar efecto")
        increase_item.connect("activate", lambda *_args: self.adjust_hover_scale(0.1))
        hover_menu.append(increase_item)
        hover_menu.append(Gtk.SeparatorMenuItem())
        for label, scale in (("Efecto 125%", 1.25), ("Efecto 150%", 1.5), ("Efecto 200%", 2.0)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item, value=scale: self.set_hover_scale(value))
            hover_menu.append(item)
        hover_item = Gtk.MenuItem(label="Agrandar al pasar")
        hover_item.set_submenu(hover_menu)
        menu.append(hover_item)

        size_menu = Gtk.Menu()
        self.add_size_item(size_menu, "Pequeno", 80, 48)
        self.add_size_item(size_menu, "Normal", DEFAULT_TILE_WIDTH, DEFAULT_TILE_HEIGHT)
        self.add_size_item(size_menu, "Grande", 160, 96)
        size_item = Gtk.MenuItem(label="Tamano")
        size_item.set_submenu(size_menu)
        menu.append(size_item)

        fps_menu = Gtk.Menu()
        for fps in (0, 1, 4, 8, 12):
            label = "0 FPS (pausado)" if fps == 0 else f"{fps} FPS"
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item, value=fps: self.set_fps(value))
            fps_menu.append(item)
        fps_menu.append(Gtk.SeparatorMenuItem())
        for seconds in (2, 5, 10, 30, 60):
            item = Gtk.MenuItem(label=f"1 frame cada {seconds}s")
            item.connect("activate", lambda _item, value=seconds: self.set_frame_interval_seconds(value))
            fps_menu.append(item)
        fps_item = Gtk.MenuItem(label="FPS")
        fps_item.set_submenu(fps_menu)
        menu.append(fps_item)

        label_menu = Gtk.Menu()
        for label, mode in (("Titulo de ventana", "title"), ("App / ejecutable", "app")):
            item = Gtk.RadioMenuItem.new_with_label_from_widget(
                label_menu.get_children()[0] if label_menu.get_children() else None,
                label,
            )
            item.set_active(self.label_mode == mode)
            item.connect("toggled", lambda check, value=mode: check.get_active() and self.update_options(label_mode=value))
            label_menu.append(item)
        label_item = Gtk.MenuItem(label="Texto mostrado")
        label_item.set_submenu(label_menu)
        menu.append(label_item)

        idle_menu = Gtk.Menu()
        for label, mode in (("Siempre visible", "off"), ("Reducir sin cursor", "collapse"), ("Ocultar sin cursor", "hide")):
            item = Gtk.RadioMenuItem.new_with_label_from_widget(
                idle_menu.get_children()[0] if idle_menu.get_children() else None,
                label,
            )
            item.set_active(self.idle_mode == mode)
            item.connect("toggled", lambda check, value=mode: check.get_active() and self.set_idle_mode(value))
            idle_menu.append(item)
        idle_item = Gtk.MenuItem(label="Sin cursor")
        idle_item.set_submenu(idle_menu)
        menu.append(idle_item)

        menu.append(Gtk.SeparatorMenuItem())
        refresh_item = Gtk.MenuItem(label="Actualizar ahora")
        refresh_item.connect("activate", lambda *_args: self.refresh_all_tiles())
        menu.append(refresh_item)

        if tile is not None:
            exclude_item = Gtk.MenuItem(label="Excluir esta ventana")
            exclude_item.connect("activate", lambda *_args: self.exclude_window(tile))
            menu.append(exclude_item)

            close_window_item = Gtk.MenuItem(label="Cerrar esta ventana")
            close_window_item.connect("activate", lambda *_args: tile.close_window())
            menu.append(close_window_item)

        if self.excluded_window_ids:
            restore_item = Gtk.MenuItem(label="Mostrar ventanas excluidas")
            restore_item.connect("activate", lambda *_args: self.restore_excluded_windows())
            menu.append(restore_item)

        close_bar_item = Gtk.MenuItem(label="Cerrar barra")
        close_bar_item.connect("activate", lambda *_args: self.win.destroy())
        menu.append(close_bar_item)

        menu.show_all()
        menu.popup_at_pointer(event)

    def add_check_item(self, menu, label, active, callback):
        item = Gtk.CheckMenuItem(label=label)
        item.set_active(bool(active))
        item.connect("toggled", lambda check: callback(check.get_active()))
        menu.append(item)

    def add_size_item(self, menu, label, width, height):
        item = Gtk.MenuItem(label=f"{label} ({width}x{height})")
        item.connect("activate", lambda *_args: self.set_tile_size(width, height))
        menu.append(item)

    def set_order_edit_mode(self, active):
        self.order_edit_mode = bool(active)
        if self.order_edit_mode:
            self.set_order_mode("manual", apply_order=False)
        for tile in self.tiles:
            tile.queue_draw()

    def set_order_mode(self, mode, apply_order=True):
        self.order_mode = normalize_order_mode(mode)
        if self.order_mode == "manual":
            self.order_edit_mode = True
        else:
            self.order_edit_mode = False
        if apply_order:
            self.apply_order()
        for tile in self.tiles:
            tile.queue_draw()

    def set_idle_mode(self, mode):
        self.idle_mode = normalize_idle_mode(mode)
        if self.idle_mode == "off":
            self.restore_from_idle()
        elif not self.pointer_inside_panel:
            self.schedule_idle_mode()

    def move_tile(self, tile, delta):
        if tile not in self.tiles or not self.tiles:
            return
        old_index = self.tiles.index(tile)
        new_index = max(0, min(len(self.tiles) - 1, old_index + int(delta)))
        if new_index == old_index:
            return
        self.set_order_mode("manual", apply_order=False)
        self.tiles.pop(old_index)
        self.tiles.insert(new_index, tile)
        self.current_columns = 0
        self.current_rows = 0
        self.fit_tiles_to_window()
        for item in self.tiles:
            item.queue_draw()

    def update_options(
        self,
        show_title=None,
        show_close=None,
        show_workspace=None,
        hover_expand=None,
        hover_mode=None,
        hover_scale=None,
        show_borders=None,
        label_mode=None,
    ):
        if show_title is not None:
            self.show_title = bool(show_title)
        if show_close is not None:
            self.show_close = bool(show_close)
        if show_workspace is not None:
            self.show_workspace = bool(show_workspace)
        if hover_mode is not None or hover_expand is not None:
            self.hover_mode = normalize_hover_mode(hover_mode, hover_expand if hover_expand is not None else self.hover_expand)
            self.hover_expand = self.hover_mode != "off"
            if hover_scale is None:
                self.hover_scale = normalize_hover_scale(None, self.hover_mode, self.hover_expand)
        if hover_scale is not None:
            self.hover_scale = normalize_hover_scale(hover_scale, self.hover_mode, self.hover_expand)
            self.hover_expand = self.hover_scale > 1.0
            if self.hover_scale <= 1.0:
                self.hover_mode = "off"
        if show_borders is not None:
            self.show_borders = bool(show_borders)
        if label_mode is not None:
            self.label_mode = normalize_label_mode(label_mode)
        for tile in self.tiles:
            tile.set_display_options(
                show_title=self.show_title,
                show_close=self.show_close,
                show_workspace=self.show_workspace,
                hover_mode=self.hover_mode,
                hover_scale=self.hover_scale,
                show_borders=self.show_borders,
                label_mode=self.label_mode,
            )
        if not self.hover_expand or self.hover_scale <= 1.0:
            self.hovered_tile = None
        self.apply_tile_size_requests()

    def set_hover_scale(self, scale):
        self.update_options(hover_scale=scale)

    def adjust_hover_scale(self, delta):
        self.set_hover_scale(self.hover_scale + float(delta))

    def set_tile_size(self, width, height):
        self.tile_width = clamp(width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        for tile in self.tiles:
            tile.set_dimensions(self.tile_width, self.tile_height)
        self.fit_tiles_to_window()

    def set_fps(self, fps):
        self.fps = max(0.0, min(12.0, float(fps)))
        self.frame_interval_seconds = None
        for tile in self.tiles:
            tile.set_fps(self.fps)

    def set_frame_interval_seconds(self, seconds):
        self.frame_interval_seconds = seconds
        for tile in self.tiles:
            tile.set_frame_interval_seconds(seconds)

    def refresh_all_tiles(self):
        for tile in self.tiles:
            tile.refresh()

    def exclude_window(self, tile):
        self.excluded_window_ids.add(int(tile.window_info.window_id))
        self.remove_tile(tile)
        self.current_columns = 0
        self.current_rows = 0
        self.fit_tiles_to_window()

    def restore_excluded_windows(self):
        self.excluded_window_ids.clear()
        self.reconcile_windows()

    def on_configure_event(self, *_args):
        self.fit_tiles_to_window()
        for tile in self.tiles:
            tile.queue_draw()
        return False

    def on_destroy(self, *_args):
        if self.window_refresh_source_id is not None:
            GLib.source_remove(self.window_refresh_source_id)
            self.window_refresh_source_id = None
        if self.active_window_source_id is not None:
            GLib.source_remove(self.active_window_source_id)
            self.active_window_source_id = None
        if self.idle_source_id is not None:
            GLib.source_remove(self.idle_source_id)
            self.idle_source_id = None
        if self.hidden_poll_source_id is not None:
            GLib.source_remove(self.hidden_poll_source_id)
            self.hidden_poll_source_id = None
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def on_key_press(self, _win, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape":
            Gtk.main_quit()
            return True
        if key in ("q", "Q") and (event.state & Gdk.ModifierType.CONTROL_MASK):
            Gtk.main_quit()
            return True
        return False
