import argparse
import re
import subprocess

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")

from gi.repository import Gdk, GdkX11


def parse_window_id(value):
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "window-id invalido: usa decimal o hexadecimal (ej: 0x4600007)"
        ) from exc


def run_command(command):
    try:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return None


def ensure_x11():
    display = Gdk.Display.get_default()
    return isinstance(display, GdkX11.X11Display)


def pick_window_id_with_xwininfo():
    proc = run_command(["xwininfo", "-int"])
    if proc is None:
        raise RuntimeError("No se encontro xwininfo. Instala xorg-xwininfo.")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "No se pudo seleccionar ventana")

    match = re.search(r"Window id:\s*(\d+)", proc.stdout)
    if not match:
        raise RuntimeError("No pude leer el id de ventana desde xwininfo")
    return int(match.group(1), 10)


def list_windows():
    proc = run_command(["wmctrl", "-lx"])
    if proc is None:
        raise RuntimeError("No se encontro wmctrl. Instala wmctrl.")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "No pude listar ventanas")

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        print("No hay ventanas visibles para listar.")
        return

    print("ID_HEX        CLASE                     TITULO")
    for line in lines:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        win_hex, _, _, wm_class, title = parts
        print(f"{win_hex:<12} {wm_class:<25} {title}")
