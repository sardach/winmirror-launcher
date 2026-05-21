import argparse
import sys

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .control_center import main as control_center_main
from .mirror import SimpleMirrorWindow
from .panel import LauncherPanelWindow
from .persistence import StateStore
from .simple_panel import (
    DEFAULT_TILE_HEIGHT,
    DEFAULT_TILE_WIDTH,
    DEFAULT_TINT2_PLACEMENT,
    DEFAULT_TINT2_SLOT_UNITS,
    MAX_TINT2_SLOT_UNITS,
    MIN_TINT2_SLOT_UNITS,
    TINT2_PLACEMENTS,
    TINT2_PROFILES,
    SimpleLauncherPanel,
    effective_tint2_placement,
)
from .smoke import MultiMirrorSmokeWindow
from .window_model import WindowInfo
from .window_registry import WindowRegistry
from .x11 import ensure_x11, parse_window_id, pick_window_id_with_xwininfo


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Barra visual de ventanas X11 con miniaturas vivas y utilidades "
            "compactas para el escritorio."
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
        default=None,
        help="Frames por segundo del espejo (default: 1)",
    )
    parser.add_argument(
        "--frame-interval-seconds",
        type=float,
        default=None,
        help="Refresca a 1 frame cada N segundos en el panel simple",
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
        default=None,
        help=f"Ancho maximo de cada espejo en el panel simple (default: {DEFAULT_TILE_WIDTH})",
    )
    parser.add_argument(
        "--tile-height",
        type=int,
        default=None,
        help=f"Alto maximo de cada espejo en el panel simple (default: {DEFAULT_TILE_HEIGHT})",
    )
    parser.add_argument(
        "--show-title",
        action="store_true",
        default=None,
        help="Muestra el titulo de la ventana sobre cada espejo del panel simple",
    )
    parser.add_argument(
        "--show-close",
        action="store_true",
        default=None,
        help="Muestra una x para cerrar la ventana real en cada espejo del panel simple",
    )
    parser.add_argument(
        "--show-workspace",
        action="store_true",
        default=None,
        help="Muestra el numero de escritorio/workspace en cada espejo del panel simple",
    )
    parser.add_argument(
        "--hover-expand",
        action="store_true",
        default=None,
        help="Agranda temporalmente el espejo al pasar el cursor",
    )
    parser.add_argument(
        "--hover-mode",
        choices=["off", "soft", "medium", "large"],
        default=None,
        help="Intensidad de agrandado al pasar el cursor en el panel simple",
    )
    parser.add_argument(
        "--hover-scale",
        type=float,
        default=None,
        help="Escala exacta del zoom visual al pasar el cursor (1.0 a 2.5)",
    )
    parser.add_argument(
        "--show-borders",
        action="store_true",
        default=None,
        help="Muestra bordes finos entre ventanas en el panel simple",
    )
    parser.add_argument(
        "--label-mode",
        choices=["title", "app"],
        default=None,
        help="Texto del overlay: titulo dinamico o app/ejecutable (default: title)",
    )
    parser.add_argument(
        "--sticky-workspaces",
        action="store_true",
        default=None,
        help="Hace que la barra del panel simple siga en todos los escritorios",
    )
    parser.add_argument(
        "--idle-mode",
        choices=["off", "collapse", "hide"],
        default=None,
        help="Comportamiento del panel simple cuando no tiene cursor",
    )
    parser.add_argument(
        "--idle-delay-ms",
        type=int,
        default=None,
        help="Demora antes de reducir/ocultar el panel simple (default: 700)",
    )
    parser.add_argument(
        "--order",
        choices=["last-used", "name", "manual"],
        default=None,
        help="Orden inicial del panel simple (default: last-used)",
    )
    parser.add_argument(
        "--exclude-window",
        action="append",
        type=parse_window_id,
        default=[],
        help="Excluye una ventana concreta del panel simple por ID decimal o hex",
    )
    parser.add_argument(
        "--show-tint2",
        action="store_true",
        default=None,
        help="Muestra una celda tint2 antes del buscador",
    )
    parser.add_argument(
        "--tint2-profile",
        choices=sorted(TINT2_PROFILES),
        default=None,
        help="Perfil tint2 inicial para la celda integrada",
    )
    parser.add_argument(
        "--tint2-units",
        type=int,
        default=None,
        help=(
            f"Cantidad de espacios que ocupa tint2 "
            f"({MIN_TINT2_SLOT_UNITS}-{MAX_TINT2_SLOT_UNITS}, default: {DEFAULT_TINT2_SLOT_UNITS})"
        ),
    )
    parser.add_argument(
        "--tint2-placement",
        choices=sorted(TINT2_PLACEMENTS),
        default=None,
        help="Ubicacion de tint2: celda interna o barra adosada al panel",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv or sys.argv[1:])
    registry = WindowRegistry()
    state_store = StateStore()
    state = state_store.load()
    fps = 1.0 if args.fps is None else args.fps

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
            fps=fps,
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
        simple_state = state.get("simple_panel") if isinstance(state.get("simple_panel"), dict) else {}
        tint2_profile = args.tint2_profile or simple_state.get("tint2_profile", "default")
        tint2_placement = effective_tint2_placement(
            tint2_profile,
            args.tint2_placement or simple_state.get("tint2_placement", DEFAULT_TINT2_PLACEMENT),
        )
        hover_mode = args.hover_mode if args.hover_mode is not None else simple_state.get("hover_mode")
        hover_expand = args.hover_expand if args.hover_expand is not None else bool(hover_mode and hover_mode != "off")
        SimpleLauncherPanel(
            windows=windows,
            tile_width=args.tile_width if args.tile_width is not None else simple_state.get("tile_width", DEFAULT_TILE_WIDTH),
            tile_height=args.tile_height if args.tile_height is not None else simple_state.get("tile_height", DEFAULT_TILE_HEIGHT),
            fps=min(args.fps if args.fps is not None else simple_state.get("fps", 1.0), 12.0),
            frame_interval_seconds=(
                args.frame_interval_seconds
                if args.frame_interval_seconds is not None
                else simple_state.get("frame_interval_seconds")
            ),
            title=args.title,
            show_title=args.show_title if args.show_title is not None else simple_state.get("show_title", False),
            show_close=args.show_close if args.show_close is not None else simple_state.get("show_close", False),
            show_workspace=(
                args.show_workspace if args.show_workspace is not None else simple_state.get("show_workspace", False)
            ),
            hover_expand=hover_expand,
            hover_mode=hover_mode,
            hover_scale=args.hover_scale if args.hover_scale is not None else simple_state.get("hover_scale"),
            show_borders=args.show_borders if args.show_borders is not None else simple_state.get("show_borders", False),
            order_mode=args.order or simple_state.get("order_mode", "last-used"),
            label_mode=args.label_mode or simple_state.get("label_mode", "title"),
            sticky_workspaces=(
                args.sticky_workspaces
                if args.sticky_workspaces is not None
                else simple_state.get("sticky_workspaces", False)
            ),
            idle_mode=args.idle_mode or simple_state.get("idle_mode", "off"),
            idle_delay_ms=args.idle_delay_ms if args.idle_delay_ms is not None else simple_state.get("idle_delay_ms", 700),
            excluded_window_ids=args.exclude_window,
            show_clock=simple_state.get("show_clock", False),
            clock_mode=simple_state.get("clock_mode", "date-time"),
            show_tint2=args.show_tint2 if args.show_tint2 is not None else simple_state.get("show_tint2", False),
            tint2_profile=tint2_profile,
            tint2_units=args.tint2_units if args.tint2_units is not None else simple_state.get("tint2_units", DEFAULT_TINT2_SLOT_UNITS),
            tint2_placement=tint2_placement,
            registry=registry,
            tint2_take_systray=simple_state.get("tint2_take_systray", False),
            state_store=state_store,
            state=state,
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
            fps=fps,
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
        fps=fps,
        title=args.title,
        always_on_top=args.always_on_top,
        no_decorations=args.no_decorations,
    )
    Gtk.main()
    return 0
