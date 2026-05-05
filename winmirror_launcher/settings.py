import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .persistence import (
    MAX_PANEL_SPACING,
    MAX_TILE_HEIGHT,
    MAX_TILE_WIDTH,
    MIN_PANEL_SPACING,
    MIN_TILE_HEIGHT,
    MIN_TILE_WIDTH,
)


class SettingsWindow:
    def __init__(self, panel):
        self.panel = panel
        self.win = Gtk.Window()
        self.win.set_title("Configurar winmirror-launcher")
        self.win.set_default_size(420, 460)
        self.win.set_transient_for(panel.win)
        self.win.set_destroy_with_parent(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        self.win.add(outer)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(10)
        outer.pack_start(grid, True, True, 0)

        self.layout_combo = self.add_combo(grid, 0, "Layout", ["horizontal", "vertical", "grid"], panel.layout_mode)
        self.panel_mode_combo = self.add_combo(grid, 1, "Modo panel", ["floating", "fixed"], panel.panel_mode)
        self.anchor_combo = self.add_combo(grid, 2, "Borde fijo", ["top", "bottom", "left", "right"], panel.anchor_edge)
        self.refresh_mode_combo = self.add_combo(grid, 3, "Refresh", ["live", "timed"], panel.refresh_mode)

        self.refresh_spin = self.add_spin(grid, 4, "Intervalo ms", panel.refresh_interval_ms, 100, 10000, 100)
        self.tile_width_spin = self.add_spin(grid, 5, "Ancho tile", panel.tile_width, MIN_TILE_WIDTH, MAX_TILE_WIDTH, 4)
        self.tile_height_spin = self.add_spin(grid, 6, "Alto tile", panel.tile_height, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, 4)
        self.spacing_spin = self.add_spin(grid, 7, "Espaciado", panel.panel_spacing, MIN_PANEL_SPACING, MAX_PANEL_SPACING, 1)

        self.workspace_check = self.add_check(grid, 8, "Mostrar workspace", panel.show_workspace_badge)
        self.title_check = self.add_check(grid, 9, "Mostrar titulo", panel.show_title)
        self.close_check = self.add_check(grid, 10, "Mostrar cerrar", panel.show_close_button)
        self.hover_check = self.add_check(grid, 11, "Hover expand", panel.hover_expand_enabled)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_end(actions, False, False, 0)

        apply_button = Gtk.Button.new_with_label("Aplicar")
        apply_button.connect("clicked", self.on_apply)
        actions.pack_end(apply_button, False, False, 0)

        close_button = Gtk.Button.new_with_label("Cerrar")
        close_button.connect("clicked", lambda *_args: self.win.destroy())
        actions.pack_end(close_button, False, False, 0)

        self.win.show_all()

    def add_combo(self, grid, row, label_text, values, active_value):
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        grid.attach(label, 0, row, 1, 1)

        combo = Gtk.ComboBoxText()
        for value in values:
            combo.append_text(value)
        combo.set_active(values.index(active_value) if active_value in values else 0)
        grid.attach(combo, 1, row, 1, 1)
        return combo

    def add_spin(self, grid, row, label_text, value, min_value, max_value, step):
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        grid.attach(label, 0, row, 1, 1)

        adjustment = Gtk.Adjustment(value=value, lower=min_value, upper=max_value, step_increment=step)
        spin = Gtk.SpinButton(adjustment=adjustment, climb_rate=1, digits=0)
        grid.attach(spin, 1, row, 1, 1)
        return spin

    def add_check(self, grid, row, label_text, active):
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        grid.attach(label, 0, row, 1, 1)

        check = Gtk.CheckButton()
        check.set_active(bool(active))
        grid.attach(check, 1, row, 1, 1)
        return check

    def on_apply(self, *_args):
        settings = {
            "layout_mode": self.layout_combo.get_active_text(),
            "panel_mode": self.panel_mode_combo.get_active_text(),
            "anchor_edge": self.anchor_combo.get_active_text(),
            "refresh_mode": self.refresh_mode_combo.get_active_text(),
            "refresh_interval_ms": self.refresh_spin.get_value_as_int(),
            "tile_width": self.tile_width_spin.get_value_as_int(),
            "tile_height": self.tile_height_spin.get_value_as_int(),
            "panel_spacing": self.spacing_spin.get_value_as_int(),
            "show_workspace_badge": self.workspace_check.get_active(),
            "show_title": self.title_check.get_active(),
            "show_close_button": self.close_check.get_active(),
            "hover_expand_enabled": self.hover_check.get_active(),
        }
        self.panel.apply_settings(settings)
