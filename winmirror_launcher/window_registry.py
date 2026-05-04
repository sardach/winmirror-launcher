from .window_model import WindowInfo
from .x11 import run_command


class WindowRegistry:
    def get_active_window_id(self):
        proc = run_command(["xdotool", "getactivewindow"])
        if proc is None or proc.returncode != 0:
            return None
        value = proc.stdout.strip()
        if not value:
            return None
        try:
            return int(value, 10)
        except ValueError:
            return None

    def get_viewability(self, window_id):
        proc = run_command(["xwininfo", "-id", str(int(window_id))])
        if proc is None or proc.returncode != 0:
            return False
        return "Map State: IsViewable" in proc.stdout

    def list_windows(self):
        proc = run_command(["wmctrl", "-lx"])
        if proc is None:
            raise RuntimeError("No se encontro wmctrl. Instala wmctrl.")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "No pude listar ventanas")

        active_window_id = self.get_active_window_id()
        windows = []
        for raw_line in proc.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split(None, 4)
            if len(parts) < 5:
                continue

            window_hex, desktop_raw, _, wm_class, title = parts

            try:
                window_id = int(window_hex, 16)
            except ValueError:
                continue

            try:
                desktop_index = int(desktop_raw, 10)
            except ValueError:
                desktop_index = -1

            windows.append(
                WindowInfo(
                    window_id=window_id,
                    window_hex=window_hex,
                    desktop_index=desktop_index,
                    wm_class=wm_class,
                    title=title,
                    is_viewable=self.get_viewability(window_id),
                    is_active=window_id == active_window_id,
                )
            )

        return windows

    def get_window(self, window_id):
        for info in self.list_windows():
            if info.window_id == int(window_id):
                return info
        return None
