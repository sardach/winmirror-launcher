# winmirror-launcher

`winmirror-launcher` es una barra visual para X11 que muestra miniaturas vivas de tus ventanas y permite usarlas como lanzador: ver, filtrar, ordenar, seleccionar, enfocar y cerrar ventanas desde un panel compacto.

El objetivo es tener una superficie de trabajo auxiliar para escritorios con muchas ventanas, ventanas apiladas o varios espacios de trabajo. Cada ventana aparece como una celda redimensionable con captura periódica; al hacer clic en una miniatura se activa la ventana real.

## Caracteristicas

- Panel visual de ventanas X11 con miniaturas capturadas desde las ventanas reales.
- Clic izquierdo para activar una ventana y clic medio para cerrarla.
- Menu contextual con opciones de visualizacion, orden, tamano, FPS e inactividad.
- Filtro de busqueda integrado como la ultima celda del panel.
- Selector manual de ventanas detectadas para decidir exactamente cuales se muestran.
- Orden por ultima app usada, por nombre o manual.
- Hover-expand configurable para agrandar columnas al pasar el cursor.
- Opciones para mostrar titulo, clase/app, workspace, bordes y boton de cerrar.
- Soporte para ventanas minimizadas u ocultas conservando la ultima captura valida.
- Reloj/fecha como celda opcional, con varios niveles de detalle.
- Celda opcional para alojar un panel `tint2` compacto con ancho configurable.
- Mini-terminales embebidas como celdas adicionales.
- Ejecutores tipo `gmrun` para lanzar comandos o scripts desde una celda del panel.
- Ventana de barra sin decoracion de Openbox por defecto.
- Modos de inactividad: siempre visible, reducir sin cursor u ocultar sin cursor.
- Opcion para hacer la barra sticky en todos los workspaces.
- Modo espejo de una sola ventana y modo smoke multi-ventana para pruebas.
- Centro de control grafico basico con `--config`.

## Requisitos

Este proyecto esta pensado para X11. Necesita herramientas habituales del escritorio X11:

- Python 3
- GTK 3 / PyGObject
- GDK X11 bindings
- VTE 2.91 para mini-terminales
- `wmctrl`
- `xdotool`
- `xwininfo`
- `xprop`
- `tint2` opcional para la celda de panel integrada

En sistemas Arch/Mabox, los paquetes suelen corresponder a nombres como `python-gobject`, `gtk3`, `vte3`, `wmctrl`, `xdotool` y `xorg-xwininfo`.

## Instalacion Local

Desde el repositorio:

```bash
./install-local.sh
```

El instalador deja el comando disponible como:

```bash
winmirror-launcher
```

Tambien instala el lanzador de escritorio si el entorno usa archivos `.desktop` en `~/.local/share/applications`.

## Uso Rapido

Abrir la barra principal:

```bash
winmirror-launcher
```

Listar ventanas detectadas:

```bash
winmirror-launcher --list
```

Abrir el centro de control:

```bash
winmirror-launcher --config
```

Abrir la barra con opciones iniciales:

```bash
winmirror-launcher --panel --tile-width 120 --tile-height 72 --fps 1
winmirror-launcher --panel --show-title --show-borders
winmirror-launcher --panel --sticky-workspaces
winmirror-launcher --panel --idle-mode collapse --idle-delay-ms 900
winmirror-launcher --panel --show-tint2 --tint2-profile default --tint2-units 3
```

Abrir un espejo de una ventana concreta:

```bash
winmirror-launcher --window-id 0x04000001
winmirror-launcher --pick
```

## Panel Principal

Si se ejecuta sin argumentos, `winmirror-launcher` abre el panel principal.

El panel se compone de celdas. Las ventanas ocupan las primeras celdas. Despues pueden aparecer mini-terminales, ejecutores, el reloj y la celda tint2. El buscador siempre ocupa la ultima celda para que nunca tape miniaturas ni quede flotando encima de otras ventanas.

El menu contextual se abre con clic derecho sobre el panel o sobre una miniatura. Desde ahi se pueden cambiar las opciones principales.

## Seleccion de Ventanas

La opcion `Seleccionar ventanas...` abre un dialogo con el total de ventanas detectadas y un checkbox por ventana. Esto permite controlar manualmente que ventanas aparecen en la barra.

El buscador filtra dentro de la seleccion activa. Si no hay resultados, el buscador conserva su propia celda para poder limpiar o cambiar la busqueda.

## Reloj y Fecha

La opcion `Hora y fecha` permite activar una celda de reloj y elegir el detalle mostrado:

- Hora
- Hora con segundos
- Fecha y hora
- Completo

Cuando esta activo sin tint2, el reloj se coloca justo antes del buscador. Si tint2 tambien esta activo, tint2 ocupa el espacio intermedio entre reloj y buscador.

## Tint2 Integrado

La opcion `Tint2` permite activar una celda de ancho configurable o una barra adosada al panel. Por defecto funciona como celda interna y ocupa 3 espacios del panel. En modo celda, los launchers se dibujan dentro de winmirror como una cuadricula real y no se lanza tint2. En modo barra adosada, winmirror genera un archivo temporal de configuracion, lanza `tint2` con ese perfil y recoloca su ventana junto al panel.

Perfiles disponibles:

- `default`: configuracion generica con menu de aplicaciones si esta disponible, mostrar escritorio, `gmrun`, taskbar compacta y bandeja del sistema.
- `chema-compact`: configuracion adaptada desde tu tint2 actual. En modo celda, winmirror dibuja tus atajos/launchers como una cuadricula adaptable porque tint2 no ajusta el launcher `L` en varias filas; la bandeja del sistema se reserva para los modos de barra adosada, donde tint2 puede funcionar como host X11 real sin comportarse como pieza flotante. Mostrar escritorio y menu inicio van en el mismo grupo de iconos que el resto de launchers; el menu inicio se ordena al extremo derecho y usa el icono personalizado del menu. En modo barra adosada usa el conjunto completo de botones, ejecutores, bandeja del sistema y launchers del panel original, sin reloj porque winmirror ya lo ofrece como celda propia.

Tambien se puede abrir directamente desde CLI:

```bash
winmirror-launcher --panel --show-tint2 --tint2-profile chema-compact --tint2-units 3
winmirror-launcher --panel --show-tint2 --tint2-placement bottom
winmirror-launcher --panel --show-tint2 --tint2-placement right
```

Desde el menu contextual se puede elegir entre 1 y 8 espacios para tint2 cuando esta como celda. Tambien se puede cambiar la ubicacion a `arriba`, `abajo`, `izquierda` o `derecha`. En `arriba` y `abajo`, tint2 se extiende por todo el ancho del panel; en `izquierda` y `derecha`, por toda la altura.

## Mini-Terminales

La opcion `Mini terminales` permite agregar una o varias terminales embebidas. Cada mini-terminal ocupa una celda del panel y lanza el shell configurado en `$SHELL`.

Opciones disponibles:

- Agregar mini terminal
- Quitar ultima
- Quitar todas

## Ejecutores

La opcion `Ejecutores` permite agregar entradas compactas tipo `gmrun`. Cada ejecutor ocupa una celda y lanza el comando escrito al presionar Enter.

Los comandos se ejecutan mediante:

```bash
/bin/sh -lc 'comando'
```

Esto permite lanzar scripts, comandos con argumentos, redirecciones y pipelines.

## Opciones Utiles

```bash
winmirror-launcher --help
winmirror-launcher --list
winmirror-launcher --panel
winmirror-launcher --panel --show-title
winmirror-launcher --panel --show-close
winmirror-launcher --panel --show-workspace
winmirror-launcher --panel --show-borders
winmirror-launcher --panel --label-mode app
winmirror-launcher --panel --order name
winmirror-launcher --panel --order manual
winmirror-launcher --panel --hover-mode medium
winmirror-launcher --panel --hover-scale 1.5
winmirror-launcher --panel --fps 4
winmirror-launcher --panel --frame-interval-seconds 10
winmirror-launcher --panel --exclude-window 0x04000001
winmirror-launcher --panel --show-tint2 --tint2-profile chema-compact --tint2-units 4
winmirror-launcher --panel --show-tint2 --tint2-placement bottom
winmirror-launcher --smoke-multi --limit 4
```

## Estado y Limitaciones

- Solo soporta X11.
- La captura depende de que el compositor/driver permita leer pixbufs de ventana.
- Las ventanas minimizadas u ocultas conservan la ultima captura valida, pero no pueden actualizar imagen mientras no sean capturables.
- Las mini-terminales requieren VTE 2.91 disponible desde PyGObject.
- La celda tint2 requiere `tint2` y `wmctrl`; la configuracion se genera como archivo temporal y se elimina al cerrar la barra.

## Licencia

GPL-3.0-or-later.

Autor: JOSE MARIA RADILLO VILLEGAS.
Aliases: SARDACH / TELTIATZIN.
