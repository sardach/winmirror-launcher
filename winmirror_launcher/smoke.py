import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk

from .tile import MirrorTile


class MultiMirrorSmokeWindow:
    def __init__(self, windows, fps, title, always_on_top, no_decorations):
        self.win = Gtk.Window()
        self.win.set_title(title or "Launcher Smoke")
        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key_press)
        self.win.set_keep_above(always_on_top)
        self.win.set_decorated(not no_decorations)
        self.win.set_default_size(960, 620)

        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.win.add(outer)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(3)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        flow.set_margin_top(10)
        flow.set_margin_bottom(10)
        flow.set_margin_start(10)
        flow.set_margin_end(10)
        outer.add(flow)

        for window_info in windows:
            tile = MirrorTile(window_info, fps=fps)
            flow.add(tile)

        self.win.show_all()

    def on_key_press(self, _win, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape":
            Gtk.main_quit()
            return True
        if key in ("q", "Q") and (event.state & Gdk.ModifierType.CONTROL_MASK):
            Gtk.main_quit()
            return True
        return False

    def on_destroy(self, *_args):
        if Gtk.main_level() > 0:
            Gtk.main_quit()
