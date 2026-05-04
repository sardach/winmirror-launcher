from .x11 import run_command


class WindowActions:
    def activate(self, window_info):
        window_id = str(int(window_info.window_id))
        proc = run_command(["xdotool", "windowactivate", "--sync", window_id])
        if proc is not None and proc.returncode == 0:
            return True

        proc = run_command(["wmctrl", "-ia", window_info.window_hex])
        return proc is not None and proc.returncode == 0

    def close(self, window_info):
        proc = run_command(["wmctrl", "-ic", window_info.window_hex])
        return proc is not None and proc.returncode == 0
