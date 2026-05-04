import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk

from .tile import MirrorTile


class SimpleMirrorWindow:
    def __init__(self, window_info, fps, title, always_on_top, no_decorations):
        self.window_info = window_info
        self.win = Gtk.Window()
        self.win.set_title(title or f"Launcher Mirror {window_info.window_hex}")
        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key_press)
        self.win.set_keep_above(always_on_top)
        self.win.set_decorated(not no_decorations)

        self.tile = MirrorTile(window_info, fps=fps)
        self.win.add(self.tile)

        sw, sh = self.tile.get_default_window_size()
        self.win.set_default_size(sw, sh + 32)
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
