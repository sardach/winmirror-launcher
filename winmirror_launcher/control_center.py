import subprocess

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .simple_panel import DEFAULT_TILE_HEIGHT, DEFAULT_TILE_WIDTH, MAX_TILE_HEIGHT, MAX_TILE_WIDTH, MIN_TILE_HEIGHT, MIN_TILE_WIDTH
from .window_registry import WindowRegistry


BIN_PATH = "/home/chema/bin/winmirror-launcher"


class ControlCenter:
    def __init__(self):
        self.registry = WindowRegistry()

        self.win = Gtk.Window()
        self.win.set_title("Winmirror Launcher")
        self.win.set_default_size(520, 460)
        self.win.connect("destroy", self.on_destroy)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        self.win.add(outer)

        controls = Gtk.Grid()
        controls.set_row_spacing(8)
        controls.set_column_spacing(10)
        outer.pack_start(controls, False, False, 0)

        self.width_spin = self.add_spin(controls, 0, "Ancho espejo", DEFAULT_TILE_WIDTH, MIN_TILE_WIDTH, MAX_TILE_WIDTH, 4)
        self.height_spin = self.add_spin(controls, 1, "Alto espejo", DEFAULT_TILE_HEIGHT, MIN_TILE_HEIGHT, MAX_TILE_HEIGHT, 4)
        self.fps_spin = self.add_spin(controls, 2, "FPS", 8, 0, 12, 1)
        self.title_check = self.add_check(controls, 3, "Mostrar nombre", False)
        self.close_check = self.add_check(controls, 4, "Mostrar cerrar", False)
        self.workspace_check = self.add_check(controls, 5, "Mostrar workspace", False)
        self.hover_check = self.add_check(controls, 6, "Agrandar al pasar", False)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(buttons, False, False, 0)

        launch_button = Gtk.Button.new_with_label("Abrir barra con estos ajustes")
        launch_button.connect("clicked", self.on_launch_simple)
        buttons.pack_start(launch_button, True, True, 0)

        stop_button = Gtk.Button.new_with_label("Cerrar barras")
        stop_button.connect("clicked", self.on_stop_panels)
        buttons.pack_start(stop_button, True, True, 0)

        self.window_list = Gtk.TextView()
        self.window_list.set_editable(False)
        self.window_list.set_cursor_visible(False)
        self.window_list.set_monospace(True)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.window_list)
        outer.pack_start(scroller, True, True, 0)

        refresh_button = Gtk.Button.new_with_label("Actualizar lista")
        refresh_button.connect("clicked", self.on_refresh_list)
        outer.pack_start(refresh_button, False, False, 0)

        self.on_refresh_list()
        self.win.show_all()

    def add_spin(self, grid, row, label_text, value, lower, upper, step):
        label = Gtk.Label(label=label_text)
        label.set_xalign(0.0)
        grid.attach(label, 0, row, 1, 1)

        adjustment = Gtk.Adjustment(value=value, lower=lower, upper=upper, step_increment=step)
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

    def on_launch_simple(self, *_args):
        command = [
            BIN_PATH,
            "--panel",
            "--tile-width",
            str(self.width_spin.get_value_as_int()),
            "--tile-height",
            str(self.height_spin.get_value_as_int()),
            "--fps",
            str(self.fps_spin.get_value_as_int()),
        ]
        if self.title_check.get_active():
            command.append("--show-title")
        if self.close_check.get_active():
            command.append("--show-close")
        if self.workspace_check.get_active():
            command.append("--show-workspace")
        if self.hover_check.get_active():
            command.append("--hover-expand")
        subprocess.Popen(command)

    def on_stop_panels(self, *_args):
        subprocess.run(["pkill", "-f", "python3 -m winmirror_launcher"], check=False)

    def on_refresh_list(self, *_args):
        try:
            windows = self.registry.list_windows()
        except RuntimeError as exc:
            text = f"Error: {exc}"
        else:
            rows = ["ID          DESK  CLASE                    TITULO"]
            for info in windows:
                title = info.title.replace("\n", " ")[:70]
                rows.append(f"{info.window_hex:<11} {info.desktop_index:<5} {info.wm_class:<24} {title}")
            text = "\n".join(rows)
        self.window_list.get_buffer().set_text(text)

    def on_destroy(self, *_args):
        if Gtk.main_level() > 0:
            Gtk.main_quit()


def main():
    ControlCenter()
    Gtk.main()
    return 0
