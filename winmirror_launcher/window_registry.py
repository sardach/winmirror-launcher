from .window_model import WindowInfo
from .x11 import run_command


ALT_TAB_EXCLUDED_STATES = {
    "_NET_WM_STATE_SKIP_TASKBAR",
}

ALT_TAB_EXCLUDED_TYPES = {
    "_NET_WM_WINDOW_TYPE_DESKTOP",
    "_NET_WM_WINDOW_TYPE_DOCK",
    "_NET_WM_WINDOW_TYPE_TOOLBAR",
    "_NET_WM_WINDOW_TYPE_MENU",
    "_NET_WM_WINDOW_TYPE_UTILITY",
    "_NET_WM_WINDOW_TYPE_SPLASH",
    "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
    "_NET_WM_WINDOW_TYPE_POPUP_MENU",
    "_NET_WM_WINDOW_TYPE_TOOLTIP",
    "_NET_WM_WINDOW_TYPE_NOTIFICATION",
    "_NET_WM_WINDOW_TYPE_COMBO",
    "_NET_WM_WINDOW_TYPE_DND",
}

ALT_TAB_INCLUDED_TYPES = {
    "_NET_WM_WINDOW_TYPE_NORMAL",
    "_NET_WM_WINDOW_TYPE_DIALOG",
}


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

    def get_window_properties(self, window_id):
        proc = run_command(
            [
                "xprop",
                "-id",
                str(int(window_id)),
                "_NET_WM_STATE",
                "_NET_WM_WINDOW_TYPE",
            ]
        )
        if proc is None or proc.returncode != 0:
            return set(), set()

        states = set()
        window_types = set()
        for line in proc.stdout.splitlines():
            if line.startswith("_NET_WM_STATE"):
                states.update(token.strip().rstrip(",") for token in line.split() if token.startswith("_NET_WM_STATE_"))
            elif line.startswith("_NET_WM_WINDOW_TYPE"):
                window_types.update(token.strip().rstrip(",") for token in line.split() if token.startswith("_NET_WM_WINDOW_TYPE_"))
        return states, window_types

    def is_alt_tab_window(self, window_id):
        states, window_types = self.get_window_properties(window_id)
        if states.intersection(ALT_TAB_EXCLUDED_STATES):
            return False
        if window_types.intersection(ALT_TAB_EXCLUDED_TYPES):
            return False
        if window_types and not window_types.intersection(ALT_TAB_INCLUDED_TYPES):
            return False
        return True

    def list_windows(self, include_non_alt_tab=False):
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

            if not include_non_alt_tab and not self.is_alt_tab_window(window_id):
                continue

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
