import argparse
import sys

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .control_center import main as control_center_main
from .mirror import SimpleMirrorWindow
from .panel import LauncherPanelWindow
from .persistence import StateStore
from .simple_panel import DEFAULT_TILE_HEIGHT, DEFAULT_TILE_WIDTH, SimpleLauncherPanel
from .smoke import MultiMirrorSmokeWindow
from .window_model import WindowInfo
from .window_registry import WindowRegistry
from .x11 import ensure_x11, parse_window_id, pick_window_id_with_xwininfo


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Base separada derivada de winmirror para evolucionar hacia un "
            "launcher visual de ventanas X11."
        )
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abre el centro de control GUI de Winmirror Launcher",
    )
    parser.add_argument(
        "--control-center",
        action="store_true",
        help="Alias de --gui",
    )
    parser.add_argument(
        "--window-id",
        type=parse_window_id,
        help="ID de ventana origen (decimal o hex, ej: 0x4600007)",
    )
    parser.add_argument(
        "--pick",
        action="store_true",
        help="Selecciona la ventana origen con el mouse (xwininfo)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista ventanas visibles y sale",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frames por segundo del espejo (default: 30)",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Titulo de la ventana espejo",
    )
    parser.add_argument(
        "--always-on-top",
        action="store_true",
        help="Mantener la ventana espejo encima",
    )
    parser.add_argument(
        "--no-decorations",
        action="store_true",
        help="Abrir sin bordes ni barra de titulo",
    )
    parser.add_argument(
        "--smoke-multi",
        action="store_true",
        help="Abre una ventana de humo con varios tiles reales",
    )
    parser.add_argument(
        "--panel",
        action="store_true",
        help="Abre el panel simple launcher explicitamente",
    )
    parser.add_argument(
        "--advanced-panel",
        action="store_true",
        help="Abre el panel experimental avanzado anterior",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Abre el centro de control GUI",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=6,
        help="Numero maximo de ventanas para --list o --smoke-multi (default: 6)",
    )
    parser.add_argument(
        "--layout",
        choices=["horizontal", "vertical", "grid"],
        default=None,
        help="Layout del panel launcher (usa estado guardado si no se indica)",
    )
    parser.add_argument(
        "--panel-mode",
        choices=["floating", "fixed"],
        default=None,
        help="Modo del panel launcher (usa estado guardado si no se indica)",
    )
    parser.add_argument(
        "--anchor-edge",
        choices=["top", "bottom", "left", "right"],
        default=None,
        help="Borde de anclaje para panel fixed (usa estado guardado si no se indica)",
    )
    parser.add_argument(
        "--hide-workspace-badge",
        action="store_true",
        help="Oculta el badge de workspace en los tiles del panel",
    )
    parser.add_argument(
        "--disable-hover-expand",
        action="store_true",
        help="Desactiva la expansion por hover en los tiles del panel",
    )
    parser.add_argument(
        "--refresh-mode",
        choices=["live", "timed"],
        default=None,
        help="Modo de refresco del panel (usa estado guardado si no se indica)",
    )
    parser.add_argument(
        "--refresh-interval-ms",
        type=int,
        default=None,
        help="Intervalo de refresco en ms para modo timed (usa estado guardado si no se indica)",
    )
    parser.add_argument(
        "--tile-width",
        type=int,
        default=DEFAULT_TILE_WIDTH,
        help=f"Ancho maximo de cada espejo en el panel simple (default: {DEFAULT_TILE_WIDTH})",
    )
    parser.add_argument(
        "--tile-height",
        type=int,
        default=DEFAULT_TILE_HEIGHT,
        help=f"Alto maximo de cada espejo en el panel simple (default: {DEFAULT_TILE_HEIGHT})",
    )
    parser.add_argument(
        "--show-title",
        action="store_true",
        help="Muestra el titulo de la ventana sobre cada espejo del panel simple",
    )
    parser.add_argument(
        "--show-close",
        action="store_true",
        help="Muestra una x para cerrar la ventana real en cada espejo del panel simple",
    )
    parser.add_argument(
        "--show-workspace",
        action="store_true",
        help="Muestra el numero de escritorio/workspace en cada espejo del panel simple",
    )
    parser.add_argument(
        "--hover-expand",
        action="store_true",
        help="Agranda temporalmente el espejo al pasar el cursor",
    )
    parser.add_argument(
        "--hover-mode",
        choices=["off", "soft", "medium", "large"],
        default=None,
        help="Intensidad de agrandado al pasar el cursor en el panel simple",
    )
    parser.add_argument(
        "--show-borders",
        action="store_true",
        help="Muestra bordes finos entre ventanas en el panel simple",
    )
    parser.add_argument(
        "--exclude-window",
        action="append",
        type=parse_window_id,
        default=[],
        help="Excluye una ventana concreta del panel simple por ID decimal o hex",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv or sys.argv[1:])
    registry = WindowRegistry()
    state_store = StateStore()
    state = state_store.load()

    if args.list:
        windows = registry.list_windows()
        if not windows:
            print("No hay ventanas visibles para listar.")
            return 0
        print("ID_HEX        CLASE                     TITULO")
        for info in windows[: max(1, args.limit)]:
            print(f"{info.window_hex:<12} {info.wm_class:<25} {info.title}")
        return 0

    if args.gui or args.control_center or args.config:
        return control_center_main()

    if not ensure_x11():
        print("winmirror-launcher solo soporta X11 por ahora.", file=sys.stderr)
        return 1

    if args.smoke_multi:
        windows = registry.list_windows()[: max(1, args.limit)]
        if not windows:
            raise RuntimeError("No hay ventanas disponibles para el smoke multi.")
        MultiMirrorSmokeWindow(
            windows=windows,
            fps=args.fps,
            title=args.title,
            always_on_top=args.always_on_top,
            no_decorations=args.no_decorations,
        )
        Gtk.main()
        return 0

    open_panel = args.panel or (
        args.window_id is None and not args.pick and not args.smoke_multi and not args.advanced_panel
    )

    if open_panel:
        windows = registry.list_windows()
        if not windows:
            raise RuntimeError("No hay ventanas disponibles para el panel.")
        SimpleLauncherPanel(
            windows=windows,
            tile_width=args.tile_width,
            tile_height=args.tile_height,
            fps=min(args.fps, 12.0),
            title=args.title,
            show_title=args.show_title,
            show_close=args.show_close,
            show_workspace=args.show_workspace,
            hover_expand=args.hover_expand,
            hover_mode=args.hover_mode,
            show_borders=args.show_borders,
            excluded_window_ids=args.exclude_window,
            registry=registry,
        )
        Gtk.main()
        return 0

    open_advanced_panel = args.advanced_panel or (
        args.window_id is None and not args.pick and not args.smoke_multi
    )

    if open_advanced_panel:
        windows = registry.list_windows()[: max(1, args.limit)]
        if not windows:
            raise RuntimeError("No hay ventanas disponibles para el panel.")

        layout_mode = args.layout or state.get("layout_mode", "horizontal")
        panel_mode = args.panel_mode or state.get("panel_mode", "floating")
        anchor_edge = args.anchor_edge or state.get("anchor_edge", "top")
        show_workspace_badge = not args.hide_workspace_badge if args.hide_workspace_badge else state.get("show_workspace_badge", True)
        show_title = state.get("show_title", False)
        show_close_button = state.get("show_close_button", False)
        hover_expand_enabled = False if args.disable_hover_expand else state.get("hover_expand_enabled", True)
        refresh_mode = args.refresh_mode or state.get("refresh_mode", "live")
        refresh_interval_ms = args.refresh_interval_ms or state.get("refresh_interval_ms", 1000)
        tile_width = state.get("tile_width", 156)
        tile_height = state.get("tile_height", 96)
        panel_spacing = state.get("panel_spacing", 6)

        preferred_order = [int(item) for item in state.get("tile_order", [])]
        by_id = {info.window_id: info for info in windows}
        ordered_windows = []
        seen = set()
        for window_id in preferred_order:
            info = by_id.get(window_id)
            if info is None:
                continue
            ordered_windows.append(info)
            seen.add(window_id)
        for info in windows:
            if info.window_id in seen:
                continue
            ordered_windows.append(info)

        panel = LauncherPanelWindow(
            windows=ordered_windows,
            fps=args.fps,
            title=args.title,
            always_on_top=args.always_on_top,
            no_decorations=args.no_decorations,
            registry=registry,
            layout_mode=layout_mode,
            panel_mode=panel_mode,
            anchor_edge=anchor_edge,
            show_workspace_badge=show_workspace_badge,
            show_title=show_title,
            show_close_button=show_close_button,
            hover_expand_enabled=hover_expand_enabled,
            refresh_mode=refresh_mode,
            refresh_interval_ms=refresh_interval_ms,
            tile_width=tile_width,
            tile_height=tile_height,
            panel_spacing=panel_spacing,
            state_store=state_store,
        )
        if args.config:
            panel.open_config_window()
        Gtk.main()
        return 0

    window_id = args.window_id
    if args.pick or window_id is None:
        print("Haz clic en la ventana que quieres espejar...")
        window_id = pick_window_id_with_xwininfo()
        print(f"Ventana seleccionada: 0x{window_id:x}")

    window_info = registry.get_window(window_id)
    if window_info is None:
        window_info = WindowInfo(
            window_id=int(window_id),
            window_hex=f"0x{int(window_id):x}",
            desktop_index=-1,
            wm_class="unknown",
            title=f"0x{int(window_id):x}",
        )

    SimpleMirrorWindow(
        window_info=window_info,
        fps=args.fps,
        title=args.title,
        always_on_top=args.always_on_top,
        no_decorations=args.no_decorations,
    )
    Gtk.main()
    return 0
