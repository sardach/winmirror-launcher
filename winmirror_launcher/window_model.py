from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    window_id: int
    window_hex: str
    desktop_index: int
    wm_class: str
    title: str
    is_viewable: bool = True
    is_active: bool = False


def format_window_line(info):
    return f"{info.window_hex:<12} {info.wm_class:<25} {info.title}"
