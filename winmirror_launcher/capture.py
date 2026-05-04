from dataclasses import dataclass

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")

from gi.repository import Gdk, GdkX11

from .x11 import run_command


@dataclass
class CaptureResult:
    state: str
    pixbuf: object | None
    message: str


class MirrorCapture:
    def __init__(self, window_id):
        self.window_id = int(window_id)
        self.source_window = None
        self.last_pixbuf = None
        self.attach()

    def attach(self):
        display = Gdk.Display.get_default()
        if display is None:
            raise RuntimeError("No hay display grafico disponible")

        source = GdkX11.X11Window.foreign_new_for_display(display, self.window_id)
        if source is None:
            raise RuntimeError(
                f"No pude abrir la ventana 0x{self.window_id:x}. "
                "Asegurate de que siga abierta."
            )

        self.source_window = source
        return source

    def get_source_size(self):
        if self.source_window is None:
            return 0, 0
        return max(1, self.source_window.get_width()), max(1, self.source_window.get_height())

    def inspect_window(self):
        proc = run_command(["xwininfo", "-id", str(self.window_id)])
        if proc is None or proc.returncode != 0:
            return {"exists": False, "is_viewable": False}
        return {
            "exists": True,
            "is_viewable": "Map State: IsViewable" in proc.stdout,
        }

    def refresh(self):
        inspection = self.inspect_window()
        if not inspection["exists"]:
            self.source_window = None
            self.last_pixbuf = None
            return CaptureResult("missing", None, "Ventana cerrada")

        if not inspection["is_viewable"]:
            self.last_pixbuf = None
            return CaptureResult("hidden", None, "Ventana minimizada u oculta")

        if self.source_window is None:
            try:
                self.attach()
            except RuntimeError:
                return CaptureResult("unavailable", None, "Ventana no disponible")

        width, height = self.get_source_size()
        if width <= 1 or height <= 1:
            self.last_pixbuf = None
            return CaptureResult("unavailable", None, "Sin superficie capturable")

        try:
            pixbuf = Gdk.pixbuf_get_from_window(self.source_window, 0, 0, width, height)
        except Exception:
            self.last_pixbuf = None
            self.source_window = None
            return CaptureResult("unavailable", None, "Captura fallida")

        if pixbuf is not None:
            self.last_pixbuf = pixbuf
            return CaptureResult("live", pixbuf, "")

        self.last_pixbuf = None
        return CaptureResult("unavailable", None, "Sin imagen disponible")
