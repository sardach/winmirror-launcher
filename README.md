# winmirror-launcher

`winmirror-launcher` es un codebase separado derivado tecnicamente de `winmirror`.

## Separacion respecto a `winmirror`

- `winmirror` original en `/home/chema/bin/winmirror` no se modifica.
- Este proyecto copia solo la base necesaria para un modo simple inicial:
  - validacion X11
  - listado de ventanas
  - seleccion por click
  - captura y espejo simple de una ventana
- Ahora incluye una primera arquitectura multi-ventana reutilizable:
  - `WindowInfo` y `WindowRegistry`
  - `MirrorCapture`
  - `MirrorTile`
  - smoke window multi-tile
  - panel horizontal utilizable con acciones de activar/cerrar
  - robustez ante ventanas cerradas/minimizadas/no capturables
  - resaltado de ventana activa
  - layout vertical para el panel
  - layout grid
  - reordenamiento manual por arrastrar y soltar
  - sincronizacion dinamica de ventanas que aparecen/desaparecen
  - modo flotante o fijo
  - persistencia de layout, geometria y orden manual
  - hover-expand opcional
  - badge de workspace opcional
  - refresco live o timed
  - defaults compactos tipo barra horizontal
  - ventana GUI de configuracion (`Ctrl+,` o `--config`)
- No incluye en esta base nueva:
  - crop
  - crop GUI
  - reenvio interactivo de mouse/teclado

## Estado actual

Esta base prueba que el nuevo paquete puede correr por si mismo antes de evolucionar al panel visual multi-ventana.

`winmirror-launcher` funciona como launcher por defecto. Si se ejecuta sin argumentos, abre el panel.

### Defaults actuales del panel

- layout horizontal
- panel flotante y movible
- barra compacta
- sin titulo por tile
- sin boton cerrar por tile
- sin badge de workspace
- sin hover-expand por defecto

## Ejemplos

```bash
winmirror-launcher --help
winmirror-launcher
winmirror-launcher --config
winmirror-launcher --list
winmirror-launcher --panel --limit 4
winmirror-launcher --panel --layout vertical --limit 4
winmirror-launcher --panel --layout grid --limit 6
winmirror-launcher --panel --panel-mode fixed --anchor-edge bottom --layout horizontal
winmirror-launcher --panel --refresh-mode timed --refresh-interval-ms 1200
winmirror-launcher --panel --hide-workspace-badge --disable-hover-expand
winmirror-launcher --smoke-multi --limit 4
winmirror-launcher --pick
winmirror-launcher --window-id 0x04000001 --always-on-top
```

## Licencia

GPL-3.0-or-later.

Autor: JOSE MARIA RADILLO VILLEGAS.
Aliases: SARDACH / TELTIATZIN.
