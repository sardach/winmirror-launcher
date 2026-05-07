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
        self.expanded_width = self.compute_expanded_width()
        self.expanded_height = self.compute_expanded_height()
        self.interval_ms = refresh_interval_ms(fps)
        self.source_window = None
        self.current_pixbuf = None
        self.status = ""
        self.show_title = bool(show_title)
        self.show_close = bool(show_close)
        self.show_workspace = bool(show_workspace)
        self.hover_expand = self.hover_mode != "off"
        self.show_borders = bool(show_borders)
        self.hovered = False

        self.set_size_request(self.tile_width, self.tile_height)
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
        self.refresh_source_id = None
        self.set_fps(fps)
        self.refresh()

    def compute_expanded_width(self):
        factor = HOVER_MODES.get(self.hover_mode, 1.0)
        return min(MAX_TILE_WIDTH, max(self.tile_width, int(round(self.tile_width * factor))))

    def compute_expanded_height(self):
        factor = HOVER_MODES.get(self.hover_mode, 1.0)
        return min(MAX_TILE_HEIGHT, max(self.tile_height, int(round(self.tile_height * factor))))

    def on_destroy(self, *_args):
        if self.refresh_source_id is not None:
            GLib.source_remove(self.refresh_source_id)
            self.refresh_source_id = None

    def set_fps(self, fps):
        self.interval_ms = refresh_interval_ms(fps)
        if self.refresh_source_id is not None:
            GLib.source_remove(self.refresh_source_id)
            self.refresh_source_id = None
        if self.interval_ms is not None:
            self.refresh_source_id = GLib.timeout_add(self.interval_ms, self.refresh)

    def set_dimensions(self, width, height):
        self.tile_width = clamp(width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        self.expanded_width = self.compute_expanded_width()
        self.expanded_height = self.compute_expanded_height()
        if self.hovered and self.hover_expand:
            self.set_size_request(self.expanded_width, self.expanded_height)
        else:
            self.set_size_request(self.tile_width, self.tile_height)
        self.queue_resize()
        self.queue_draw()

    def set_display_options(
        self,
        show_title=None,
        show_close=None,
        show_workspace=None,
        hover_expand=None,
        hover_mode=None,
        show_borders=None,
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
        if show_borders is not None:
            self.show_borders = bool(show_borders)
        self.set_dimensions(self.tile_width, self.tile_height)

    def attach_source(self):
        display = Gdk.Display.get_default()
        if display is None:
            self.status = "sin display"
            return False
        self.source_window = GdkX11.X11Window.foreign_new_for_display(
            display,
            int(self.window_info.window_id),
        )
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
            return True
        proc = run_command(["wmctrl", "-ia", self.window_info.window_hex])
        return proc is not None and proc.returncode == 0

    def close_window(self):
        proc = run_command(["wmctrl", "-ic", self.window_info.window_hex])
        return proc is not None and proc.returncode == 0

    def on_button_press(self, _widget, event):
        if int(event.button) == 3 and self.panel is not None:
            self.panel.show_context_menu(event, self)
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

    def on_enter(self, *_args):
        self.hovered = True
        if self.hover_expand:
            self.set_size_request(self.expanded_width, self.expanded_height)
            self.queue_resize()
        return False

    def on_leave(self, *_args):
        self.hovered = False
        if self.hover_expand:
            self.set_size_request(self.tile_width, self.tile_height)
            self.queue_resize()
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

        if self.hovered and self.hover_mode != "off":
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
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
            title = self.window_info.title[:42]
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
        title = self.window_info.title or self.window_info.wm_class or self.window_info.window_hex
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
        fps=8.0,
        title=None,
        show_title=False,
        show_close=False,
        show_workspace=False,
        hover_expand=False,
        hover_mode=None,
        show_borders=False,
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
        self.show_borders = bool(show_borders)
        self.window_refresh_source_id = None

        self.win = Gtk.Window()
        self.win.set_title(title or "winmirror-launcher")
        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key_press)
        self.win.set_resizable(True)
        self.win.set_decorated(True)
        self.win.connect("configure-event", self.on_configure_event)
        self.win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.win.connect("button-press-event", self.on_panel_button_press)

        screen = Gdk.Screen.get_default()
        screen_width = screen.get_width() if screen is not None else 1200
        target_width = min(max(self.tile_width, len(windows) * self.tile_width), max(360, screen_width - 80))
        target_height = self.tile_height
        self.win.set_default_size(target_width, target_height)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroller.set_shadow_type(Gtk.ShadowType.NONE)
        self.win.add(scroller)

        self.scroller = scroller
        self.strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.strip.set_margin_top(0)
        self.strip.set_margin_bottom(0)
        self.strip.set_margin_start(0)
        self.strip.set_margin_end(0)
        scroller.add(self.strip)

        self.tiles = []
        for info in self.filter_windows(windows):
            self.add_tile(info)

        self.win.show_all()
        self.capture_own_window_id()
        self.fit_tiles_to_current_width()
        self.window_refresh_source_id = GLib.timeout_add(WINDOW_REFRESH_MS, self.reconcile_windows)

    def capture_own_window_id(self):
        gdk_window = self.win.get_window()
        if gdk_window is None:
            return
        try:
            self.own_window_id = int(gdk_window.get_xid())
        except AttributeError:
            self.own_window_id = None

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
            show_title=self.show_title,
            show_close=self.show_close,
            show_workspace=self.show_workspace,
            hover_mode=self.hover_mode,
            show_borders=self.show_borders,
            panel=self,
        )
        self.strip.pack_start(tile, False, False, 0)
        self.tiles.append(tile)
        tile.show_all()
        return tile

    def remove_tile(self, tile):
        if tile in self.tiles:
            self.tiles.remove(tile)
        self.strip.remove(tile)
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

        after_ids = [tile.window_info.window_id for tile in self.tiles]
        if before_ids != after_ids:
            self.fit_tiles_to_current_width()
        return True

    def fit_tiles_to_current_width(self):
        if not self.tiles:
            return
        alloc = self.scroller.get_allocation()
        width = alloc.width or self.win.get_allocation().width
        if width <= 1:
            return
        target_width = clamp(width // len(self.tiles), MIN_TILE_WIDTH, MAX_TILE_WIDTH, self.tile_width)
        self.tile_width = target_width
        for tile in self.tiles:
            tile.set_dimensions(self.tile_width, self.tile_height)

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
        menu.append(Gtk.SeparatorMenuItem())

        hover_menu = Gtk.Menu()
        for label, mode in (("Sin agrandar", "off"), ("Suave", "soft"), ("Medio", "medium"), ("Grande", "large")):
            item = Gtk.RadioMenuItem.new_with_label_from_widget(
                hover_menu.get_children()[0] if hover_menu.get_children() else None,
                label,
            )
            item.set_active(self.hover_mode == mode)
            item.connect("toggled", lambda check, value=mode: check.get_active() and self.update_options(hover_mode=value))
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
        fps_item = Gtk.MenuItem(label="FPS")
        fps_item.set_submenu(fps_menu)
        menu.append(fps_item)

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

    def update_options(
        self,
        show_title=None,
        show_close=None,
        show_workspace=None,
        hover_expand=None,
        hover_mode=None,
        show_borders=None,
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
        if show_borders is not None:
            self.show_borders = bool(show_borders)
        for tile in self.tiles:
            tile.set_display_options(
                show_title=self.show_title,
                show_close=self.show_close,
                show_workspace=self.show_workspace,
                hover_mode=self.hover_mode,
                show_borders=self.show_borders,
            )

    def set_tile_size(self, width, height):
        self.tile_width = clamp(width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, DEFAULT_TILE_WIDTH)
        self.tile_height = clamp(height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, DEFAULT_TILE_HEIGHT)
        for tile in self.tiles:
            tile.set_dimensions(self.tile_width, self.tile_height)
        screen = Gdk.Screen.get_default()
        screen_width = screen.get_width() if screen is not None else 1200
        target_width = min(max(self.tile_width, len(self.tiles) * self.tile_width), max(360, screen_width - 80))
        self.win.resize(target_width, self.tile_height)

    def set_fps(self, fps):
        self.fps = max(1.0, min(12.0, float(fps)))
        for tile in self.tiles:
            tile.set_fps(self.fps)

    def refresh_all_tiles(self):
        for tile in self.tiles:
            tile.refresh()

    def exclude_window(self, tile):
        self.excluded_window_ids.add(int(tile.window_info.window_id))
        self.remove_tile(tile)
        self.fit_tiles_to_current_width()

    def restore_excluded_windows(self):
        self.excluded_window_ids.clear()
        self.reconcile_windows()

    def on_configure_event(self, *_args):
        self.fit_tiles_to_current_width()
        for tile in self.tiles:
            tile.queue_draw()
        return False

    def on_destroy(self, *_args):
        if self.window_refresh_source_id is not None:
            GLib.source_remove(self.window_refresh_source_id)
            self.window_refresh_source_id = None
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
