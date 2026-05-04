import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GObject", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gdk, GLib, GObject, Gtk, Pango, PangoCairo

from .capture import MirrorCapture


class MirrorTile(Gtk.Box):
    __gsignals__ = {
        "activate-requested": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (object,),
        ),
        "close-requested": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (object,),
        ),
        "reorder-requested": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (int, int),
        ),
    }

    def __init__(
        self,
        window_info,
        fps=30.0,
        title_visible=True,
        show_close=False,
        show_workspace_badge=True,
        hover_expand_enabled=True,
        refresh_mode="live",
        refresh_interval_ms=1000,
        tile_width=220,
        tile_height=160,
        panel_spacing=4,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=panel_spacing)
        self.window_info = window_info
        self.refresh_mode = refresh_mode
        self.refresh_interval_ms = int(refresh_interval_ms)
        if refresh_mode == "timed":
            self.interval_ms = max(100, self.refresh_interval_ms)
        else:
            self.interval_ms = max(15, int(round(1000.0 / max(1.0, fps))))
        self.capture = MirrorCapture(window_info.window_id)
        self.current_pixbuf = None
        self.capture_enabled = True
        self.capture_state = "idle"
        self.status_message = "Esperando imagen..."
        self.is_active = bool(window_info.is_active)
        self.refresh_count = 0
        self.show_workspace_badge = show_workspace_badge
        self.hover_expand_enabled = hover_expand_enabled
        self.hover_expanded = False
        self.base_width = int(tile_width)
        self.base_height = int(tile_height)
        self.expanded_width = max(self.base_width + 36, int(round(self.base_width * 1.22)))
        self.expanded_height = max(self.base_height + 24, int(round(self.base_height * 1.18)))

        self.set_size_request(self.base_width, self.base_height)
        self.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [],
            Gdk.DragAction.MOVE,
        )
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE)
        target = Gtk.TargetEntry.new("WINMIRROR_TILE", Gtk.TargetFlags.SAME_APP, 0)
        self.drag_source_set_target_list(Gtk.TargetList.new([target]))
        self.drag_dest_set_target_list(Gtk.TargetList.new([target]))
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.pack_start(header, False, False, 0)

        if show_workspace_badge:
            self.workspace_badge = Gtk.Label()
            self.workspace_badge.set_text(self._build_workspace_badge_text())
            self.workspace_badge.set_xalign(0.0)
            header.pack_start(self.workspace_badge, False, False, 0)
        else:
            self.workspace_badge = None

        self.label = Gtk.Label()
        self.label.set_xalign(0.0)
        self.label.set_hexpand(True)
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(28)
        self.title_visible = title_visible
        self.label.set_text(self._build_label_text() if self.title_visible else "")
        header.pack_start(self.label, True, True, 0)

        if show_close:
            self.close_button = Gtk.Button.new_with_label("x")
            self.close_button.set_relief(Gtk.ReliefStyle.NONE)
            self.close_button.set_focus_on_click(False)
            self.close_button.set_tooltip_text("Cerrar ventana real")
            self.close_button.connect("clicked", self.on_close_clicked)
            header.pack_end(self.close_button, False, False, 0)
        else:
            self.close_button = None

        self.preview_button = Gtk.Button()
        self.preview_button.set_relief(Gtk.ReliefStyle.NONE)
        self.preview_button.set_focus_on_click(False)
        self.preview_button.connect("clicked", self.on_activate_clicked)
        self.preview_button.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.preview_button.connect("enter-notify-event", self.on_hover_enter)
        self.preview_button.connect("leave-notify-event", self.on_hover_leave)
        self.pack_start(self.preview_button, True, True, 0)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(self.base_width, max(56, self.base_height - 28))
        self.area.connect("draw", self.on_draw)
        self.preview_button.add(self.area)

        GLib.timeout_add(self.interval_ms, self.refresh_frame)

    def _build_label_text(self):
        return self.window_info.title

    def _build_workspace_badge_text(self):
        return f"[{self.window_info.desktop_index}]"

    def refresh_frame(self):
        if not self.capture_enabled:
            return False
        result = self.capture.refresh()
        self.refresh_count += 1
        self.capture_state = result.state
        self.status_message = result.message or "Esperando imagen..."
        self.current_pixbuf = result.pixbuf
        if result.state == "missing":
            self.stop_capture(result.message)
            return False
        self.area.queue_draw()
        return True

    def get_default_window_size(self):
        width, height = self.capture.get_source_size()
        return max(320, width), max(200, height)

    def on_activate_clicked(self, _button):
        self.emit("activate-requested", self.window_info)

    def on_close_clicked(self, _button):
        self.emit("close-requested", self.window_info)

    def stop_capture(self, message="Ventana cerrada"):
        self.capture_enabled = False
        self.capture_state = "missing"
        self.current_pixbuf = None
        self.status_message = message
        if self.title_visible:
            self.label.set_text(message)
        if self.close_button is not None:
            self.close_button.set_sensitive(False)
        self.preview_button.set_sensitive(False)
        self.area.queue_draw()

    def update_window_info(self, window_info):
        self.window_info = window_info
        self.is_active = bool(window_info.is_active)
        if self.capture_enabled:
            if self.title_visible:
                self.label.set_text(self._build_label_text())
            if self.workspace_badge is not None:
                self.workspace_badge.set_text(self._build_workspace_badge_text())
        self.area.queue_draw()

    def set_active(self, is_active):
        self.is_active = bool(is_active)
        self.area.queue_draw()

    def on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        width = max(1, alloc.width)
        height = max(1, alloc.height)

        cr.set_source_rgb(0.05, 0.05, 0.05)
        cr.paint()

        if self.current_pixbuf is None:
            self.draw_center_text(cr, width, height, self.status_message)
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
        self.draw_border(cr, width, height)
        return False

    def draw_border(self, cr, width, height):
        cr.save()
        if self.is_active:
            cr.set_source_rgb(1.0, 0.65, 0.1)
            cr.set_line_width(3.0)
        elif self.capture_state in ("hidden", "unavailable", "missing"):
            cr.set_source_rgb(0.75, 0.3, 0.2)
            cr.set_line_width(2.0)
        else:
            cr.set_source_rgb(0.35, 0.35, 0.35)
            cr.set_line_width(1.5)
        cr.rectangle(1.5, 1.5, max(0, width - 3.0), max(0, height - 3.0))
        cr.stroke()
        cr.restore()

    def draw_center_text(self, cr, width, height, text):
        layout = self.area.create_pango_layout(text)
        layout.set_font_description(Pango.FontDescription("Sans 10"))
        tw, th = layout.get_pixel_size()
        cr.set_source_rgb(0.8, 0.8, 0.8)
        cr.move_to((width - tw) / 2.0, (height - th) / 2.0)
        PangoCairo.show_layout(cr, layout)

    def on_drag_data_get(self, _widget, _context, selection_data, _info, _time):
        selection_data.set_text(str(self.window_info.window_id), -1)

    def on_drag_data_received(self, _widget, _context, _x, _y, selection_data, _info, time):
        text = selection_data.get_text()
        if not text:
            Gtk.drag_finish(_context, False, False, time)
            return

        try:
            source_id = int(text)
        except ValueError:
            Gtk.drag_finish(_context, False, False, time)
            return

        target_id = int(self.window_info.window_id)
        if source_id != target_id:
            self.emit("reorder-requested", source_id, target_id)
        Gtk.drag_finish(_context, True, True, time)

    def on_hover_enter(self, *_args):
        self.set_hover_expanded(True)
        return False

    def on_hover_leave(self, *_args):
        self.set_hover_expanded(False)
        return False

    def set_hover_expanded(self, expanded):
        if not self.hover_expand_enabled:
            expanded = False
        expanded = bool(expanded)
        if self.hover_expanded == expanded:
            return
        self.hover_expanded = expanded
        width = self.expanded_width if expanded else self.base_width
        height = self.expanded_height if expanded else self.base_height
        preview_height = max(56, height - 28)
        self.set_size_request(width, height)
        self.area.set_size_request(width, preview_height)
        self.queue_resize()
