"""
view.py  —  Visualizador paso a paso del Sudoku 9 Tableros
============================================================
Importa sudoku directamente y muestra:
  • Layout de los 9 tableros (posición fiel al dibujo original)
  • Animación celda por celda de la ruta de solución
  • Panel de estadísticas en tiempo real
  • Barra de progreso y controles de velocidad

Uso:
    python view.py                        # parámetros por defecto
    python view.py --semilla 7 --pct 0.12 --delay 0.05
"""

import sys
import os
import copy
import argparse
import time
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import matplotlib
matplotlib.use("TkAgg")          # cambiar a "Agg" si no hay display
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
from matplotlib.widgets import Button, Slider
import numpy as np

# ── importar el motor ────────────────────────────────────────────────────────
from utils.sudoku import (
    generar_estado_aleatorio,
    ArbolBuscadorAStar,
)



# ============================================================================
# LAYOUT: posición (fila_panel, col_panel) de cada tablero en la cuadrícula
# visual 5×5, fiel al dibujo de referencia.
#
#    col  0    1    2    3    4
# fila
#  0    [ 5]  [ 1]  --  [ 2]  [ 6]
#  1    [ 1]  [ 0]  --  [ 0]  [ 2]   ← partes solapadas (no se dibujan doble)
#  2     --   [ 0]  --  [ 0]   --
#  3    [ 3]  [ 0]  --  [ 0]  [ 4]
#  4    [ 7]  [ 3]  --  [ 4]  [ 8]
#
# Usamos una grilla de 5 filas × 5 columnas de subplots.
# Cada tablero ocupa UN subplot. Los huecos quedan ocultos.
# ============================================================================

# (tablero_id) → (row_en_grilla, col_en_grilla)
GRID_POS = {
    0: (2, 2),   # Centro
    1: (1, 1),   # Interno arriba-izquierda
    2: (1, 3),   # Interno arriba-derecha
    3: (3, 1),   # Interno abajo-izquierda
    4: (3, 3),   # Interno abajo-derecha
    5: (0, 0),   # Externo arriba-izquierda
    6: (0, 4),   # Externo arriba-derecha
    7: (4, 0),   # Externo abajo-izquierda
    8: (4, 4),   # Externo abajo-derecha
}

# Colores
COLOR_FIJO      = "#378668"   # azul oscuro  — celda prellenada
COLOR_NUEVO     = "#e94560"   # rojo vivo    — última celda colocada
COLOR_ESPEJO    = "#f5a623"   # naranja      — celda propagada por espejo
COLOR_NORMAL    = "#23376e"   # azul medio   — celda resuelta normal
COLOR_VACIO     = "#9fb5cf"   # azul profundo — celda vacía
COLOR_GRID_BG   = "#5353c5"
COLOR_TEXT_FIJO = "#e0e0ff"
COLOR_TEXT_NEW  = "#ffffff"
COLOR_BORDER    = "#53d8fb"


# ============================================================================
# DIBUJADOR DE UN TABLERO 9×9
# ============================================================================

def dibujar_tablero(ax, grid_z, fijas, ultimo=None, espejos=None, titulo=""):
    """
    Dibuja el tablero `grid_z` en el Axes `ax`.
    fijas   : set de (x,y) prellenadas
    ultimo  : (x,y) última celda colocada
    espejos : set de (x,y) propagadas como espejo en este tablero
    """
    ax.clear()
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 9)
    ax.set_aspect("equal")
    ax.set_facecolor(COLOR_GRID_BG)
    ax.set_title(titulo, fontsize=7, color=COLOR_BORDER,
                 fontweight="bold", pad=3)
    ax.tick_params(left=False, bottom=False,
                   labelleft=False, labelbottom=False)

    espejos = espejos or set()

    for x in range(9):
        for y in range(9):
            val = grid_z[x][y]
            celda_xy = (x, y)

            # color de fondo
            if celda_xy == ultimo:
                bg = COLOR_NUEVO
            elif celda_xy in espejos:
                bg = COLOR_ESPEJO
            elif celda_xy in fijas:
                bg = COLOR_FIJO
            elif val != 0:
                bg = COLOR_NORMAL
            else:
                bg = COLOR_VACIO

            rect = patches.FancyBboxPatch(
                (y + 0.05, 8 - x + 0.05),
                0.90, 0.90,
                boxstyle="round,pad=0.04",
                facecolor=bg,
                edgecolor="#1e1e3a",
                linewidth=0.4,
            )
            ax.add_patch(rect)

            if val != 0:
                color_txt = COLOR_TEXT_NEW if celda_xy in (
                    {ultimo} | espejos) else COLOR_TEXT_FIJO
                ax.text(
                    y + 0.5, 8 - x + 0.5, str(val),
                    ha="center", va="center",
                    fontsize=7, fontweight="bold",
                    color=color_txt,
                )

    # líneas de subcuadros 3×3
    for k in range(0, 10, 3):
        lw_bold = 1.2
        ax.axhline(k, color=COLOR_BORDER, linewidth=lw_bold, alpha=0.6)
        ax.axvline(k, color=COLOR_BORDER, linewidth=lw_bold, alpha=0.6)

    # líneas finas
    for k in range(10):
        if k % 3 != 0:
            ax.axhline(k, color="#2a2a4a", linewidth=0.3)
            ax.axvline(k, color="#2a2a4a", linewidth=0.3)


# ============================================================================
# VISUALIZADOR PRINCIPAL
# ============================================================================

class Visualizador:

    def __init__(self, estado_inicial, celdas_fijas,
                 ruta, estado_resuelto, stats):

        self.estado_inicial  = estado_inicial
        self.estado_resuelto = estado_resuelto
        self.ruta            = ruta          # lista de dicts con operador
        self.stats           = stats
        self.paso_actual     = 0
        self.total_pasos     = len(ruta)
        self.reproduciendo   = False
        self.delay           = 0.3          # segundos entre pasos
        self._timer          = None             # timer matplotlib

        # conjuntos de celdas fijas por tablero
        self.fijas = {}
        for z in range(9):
            self.fijas[z] = set()
        for (z, x, y) in celdas_fijas:
            self.fijas[z].add((x, y))

        # estado mutable que iremos actualizando
        self.grid_actual = copy.deepcopy(estado_inicial.grid)

        self._construir_figura()
        self._dibujar_todo()

    # ── construcción de la figura ────────────────────────────────────────────

    def _construir_figura(self):
        self.fig = plt.figure(figsize=(16, 11), facecolor=COLOR_GRID_BG)
        self.fig.canvas.manager.set_window_title(
            "Sudoku 9 Tableros — Visualizador A*")

        # grilla principal 5×5 para los tableros
        gs_main = GridSpec(
            5, 5,
            figure=self.fig,
            left=0.01, right=0.72,
            top=0.95, bottom=0.12,
            hspace=0.45, wspace=0.35,
        )

        self.axes = {}
        for z, (row, col) in GRID_POS.items():
            ax = self.fig.add_subplot(gs_main[row, col])
            self.axes[z] = ax

        # panel lateral derecho
        gs_side = GridSpec(
            6, 1,
            figure=self.fig,
            left=0.74, right=0.97,
            top=0.95, bottom=0.12,
            hspace=0.6,
        )

        self.ax_info   = self.fig.add_subplot(gs_side[0:3, 0])
        self.ax_prog   = self.fig.add_subplot(gs_side[3, 0])
        self.ax_leyend = self.fig.add_subplot(gs_side[4:6, 0])

        for ax in [self.ax_info, self.ax_prog, self.ax_leyend]:
            ax.set_facecolor(COLOR_GRID_BG)
            ax.axis("off")

        # botones y slider (zona inferior)
        self.ax_btn_prev  = self.fig.add_axes([0.08, 0.03, 0.08, 0.045])
        self.ax_btn_play  = self.fig.add_axes([0.18, 0.03, 0.10, 0.045])
        self.ax_btn_next  = self.fig.add_axes([0.30, 0.03, 0.08, 0.045])
        self.ax_btn_reset = self.fig.add_axes([0.40, 0.03, 0.08, 0.045])
        self.ax_slider    = self.fig.add_axes([0.52, 0.035, 0.18, 0.025])

        btn_kw = dict(color="#1a1a3a", hovercolor="#e94560")
        self.btn_prev  = Button(self.ax_btn_prev,  "◀ Prev",  **btn_kw)
        self.btn_play  = Button(self.ax_btn_play,  "▶ PLAYY",  color="#064935", hovercolor="#e94560")
        self.btn_next  = Button(self.ax_btn_next,  "Next ▶",  **btn_kw)
        self.btn_reset = Button(self.ax_btn_reset, "↺ Reset", **btn_kw)
        self.slider    = Slider(
            self.ax_slider, "Velocidad", 0.2, 1.0,
            valinit=self.delay, color="#53d8fb",
        )

        for btn in [self.btn_prev, self.btn_play,
                    self.btn_next, self.btn_reset]:
            btn.label.set_color("white")
            btn.label.set_fontsize(9)

        self.btn_prev.on_clicked(self._on_prev)
        self.btn_play.on_clicked(self._on_play)
        self.btn_next.on_clicked(self._on_next)
        self.btn_reset.on_clicked(self._on_reset)
        self.slider.on_changed(self._on_slider)

        # título general
        self.fig.text(
            0.385, 0.975,
            "SUDOKU 9 TABLEROS  ·  Búsqueda A*",
            ha="center", va="top",
            fontsize=13, color=COLOR_BORDER,
            fontweight="bold",
            fontfamily="monospace",
        )

    # ── dibujo completo ──────────────────────────────────────────────────────

    def _dibujar_todo(self, ultimo_op=None, espejos_op=None):
        espejos_op = espejos_op or {}   # {z: set of (x,y)}

        for z in range(9):
            ult = None
            if ultimo_op and ultimo_op[0] == z:
                ult = (ultimo_op[1], ultimo_op[2])

            dibujar_tablero(
                self.axes[z],
                self.grid_actual[z],
                self.fijas[z],
                ultimo=ult,
                espejos=espejos_op.get(z, set()),
                titulo=f"Tablero {z}",
            )

        self._dibujar_info(ultimo_op)
        self._dibujar_progreso()
        self._dibujar_leyenda()
        self.fig.canvas.draw_idle()

    # ── panel de información ─────────────────────────────────────────────────

    def _dibujar_info(self, ultimo_op=None):
        ax = self.ax_info
        ax.clear()
        ax.set_facecolor("#0d0d1f")
        ax.axis("off")

        vacias = sum(
            1 for z in range(9)
            for x in range(9)
            for y in range(9)
            if self.grid_actual[z][x][y] == 0
        )
        llenadas = 729 - vacias

        lines = [
            ("ESTADÍSTICAS A*", None, 10, COLOR_BORDER),
            ("", None, 6, "white"),
            (f"Paso        {self.paso_actual} / {self.total_pasos}",
             None, 8, "white"),
            (f"Celdas llenas   {llenadas} / 729",
             None, 8, "#53d8fb"),
            (f"Celdas vacías   {vacias}",
             None, 8, "#aaaacc"),
            ("", None, 4, "white"),
            (f"Nodos abiertos  {self.stats.get('abiertos', '?')}",
             None, 8, "white"),
            (f"Nodos cerrados  {self.stats.get('cerrados', '?')}",
             None, 8, "white"),
            (f"Backtracks      {self.stats.get('backtracks', '?')}",
             None, 8, "#f5a623"),
            (f"Tiempo búsq.    {self.stats.get('tiempo', '?')}s",
             None, 8, "white"),
            (f"b* efectivo     {self.stats.get('beff', '?')}",
             None, 8, "#e94560"),
        ]

        if ultimo_op:
            z, x, y, v = ultimo_op
            lines += [
                ("", None, 6, "white"),
                ("ÚLTIMO OPERADOR", None, 9, COLOR_BORDER),
                (f"Tablero {z}  fila {x}  col {y}", None, 8, "#f5a623"),
                (f"→  valor  {v}", None, 10, COLOR_NUEVO),
            ]

        y_pos = 0.97
        for text, _, fsize, color in lines:
            ax.text(0.05, y_pos, text, transform=ax.transAxes,
                    fontsize=fsize, color=color, va="top",
                    fontfamily="monospace")
            y_pos -= 0.072

    # ── barra de progreso ────────────────────────────────────────────────────

    def _dibujar_progreso(self):
        ax = self.ax_prog
        ax.clear()
        ax.set_facecolor(COLOR_GRID_BG)
        ax.axis("off")

        pct = self.paso_actual / max(self.total_pasos, 1)
        bar_w = 0.90
        ax.add_patch(patches.FancyBboxPatch(
            (0.05, 0.3), bar_w, 0.4,
            boxstyle="round,pad=0.02",
            facecolor="#1a1a3a", edgecolor=COLOR_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False,
        ))
        if pct > 0:
            ax.add_patch(patches.FancyBboxPatch(
                (0.05, 0.3), bar_w * pct, 0.4,
                boxstyle="round,pad=0.02",
                facecolor=COLOR_NUEVO if pct < 1 else "#00ff88",
                edgecolor="none",
                transform=ax.transAxes, clip_on=False,
            ))
        ax.text(0.5, 0.82, f"{pct*100:.1f}%  completado",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=8, color="white", fontfamily="monospace")

    # ── leyenda de colores ───────────────────────────────────────────────────

    def _dibujar_leyenda(self):
        ax = self.ax_leyend
        ax.clear()
        ax.set_facecolor(COLOR_GRID_BG)
        ax.axis("off")

        items = [
            (COLOR_FIJO,   "Celda inicial (fija)"),
            (COLOR_NUEVO,  "Último valor colocado"),
            (COLOR_ESPEJO, "Espejo propagado"),
            (COLOR_NORMAL, "Valor resuelto"),
            (COLOR_VACIO,  "Celda vacía"),
        ]
        ax.text(0.05, 0.97, "LEYENDA", transform=ax.transAxes,
                fontsize=9, color=COLOR_BORDER, fontweight="bold",
                fontfamily="monospace", va="top")
        for i, (color, label) in enumerate(items):
            y = 0.82 - i * 0.17
            ax.add_patch(patches.FancyBboxPatch(
                (0.05, y - 0.05), 0.14, 0.11,
                boxstyle="round,pad=0.02",
                facecolor=color, edgecolor="#333355",
                transform=ax.transAxes, clip_on=False,
            ))
            ax.text(0.24, y + 0.01, label, transform=ax.transAxes,
                    fontsize=7.5, color="white", va="center",
                    fontfamily="monospace")

    # ── aplicar paso ─────────────────────────────────────────────────────────

    def _aplicar_paso(self, n):
        """Reconstruye grid_actual hasta el paso n."""
        self.grid_actual = copy.deepcopy(self.estado_inicial.grid)
        for i in range(n):
            op = self.ruta[i]["operador"]
            z, x, y, v = op
            self.grid_actual[z][x][y] = v
            # propagar espejos
            from utils.sudoku import CONEXIONES
            if (z, x, y) in CONEXIONES:
                for (ze, xe, ye) in CONEXIONES[(z, x, y)]:
                    self.grid_actual[ze][xe][ye] = v

    def _espejos_de_op(self, op):
        """Devuelve {z: set(x,y)} de los espejos del operador op."""
        from utils.sudoku import CONEXIONES
        result = {}
        if op is None:
            return result
        z, x, y, _ = op
        if (z, x, y) in CONEXIONES:
            for (ze, xe, ye) in CONEXIONES[(z, x, y)]:
                result.setdefault(ze, set()).add((xe, ye))
        return result

    def _ir_a_paso(self, n):
        n = max(0, min(n, self.total_pasos))
        self.paso_actual = n
        self._aplicar_paso(n)
        op = self.ruta[n - 1]["operador"] if n > 0 else None
        espejos = self._espejos_de_op(op)
        self._dibujar_todo(ultimo_op=op, espejos_op=espejos)

    # ── callbacks de botones ─────────────────────────────────────────────────

    def _on_prev(self, event):
        self.reproduciendo = False
        self.btn_play.label.set_text("▶ Play")
        self._ir_a_paso(self.paso_actual - 1)

    def _on_next(self, event):
        self.reproduciendo = False
        self.btn_play.label.set_text("▶ Play")
        self._ir_a_paso(self.paso_actual + 1)

    def _on_reset(self, event):
        self.reproduciendo = False
        self.btn_play.label.set_text("▶ Play")
        self._ir_a_paso(0)

    def _on_play(self, event):
        if self.reproduciendo:
            # pausar: detener el timer
            self.reproduciendo = False
            self.btn_play.label.set_text("▶ Play")
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
        else:
            # reproducir: arrancar el timer
            self.reproduciendo = True
            self.btn_play.label.set_text("⏸ Pausa")
            self._arrancar_timer()

    def _on_slider(self, val):
        # val va de 0.01 (rápido) a 0.5 (lento) en segundos
        self.delay = val
        # si está reproduciendo, reiniciar el timer con el nuevo intervalo
        if self.reproduciendo and self._timer is not None:
            self._timer.stop()
            self._arrancar_timer()

    def _arrancar_timer(self):
        """Crea y arranca un timer de matplotlib (no bloquea el event loop)."""
        intervalo_ms = int(self.delay * 1000)
        self._timer = self.fig.canvas.new_timer(interval=intervalo_ms)
        self._timer.add_callback(self._tick_timer)
        self._timer.start()

    def _tick_timer(self):
        """Callback del timer: avanza un paso por disparo."""
        if not self.reproduciendo or self.paso_actual >= self.total_pasos:
            self.reproduciendo = False
            self.btn_play.label.set_text("▶ Play")
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self.fig.canvas.draw_idle()
            return
        self._ir_a_paso(self.paso_actual + 1)

    # ── mostrar ──────────────────────────────────────────────────────────────

    def mostrar(self):
        plt.show()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Visualizador paso a paso del Sudoku 9 Tableros con A*"
    )
    parser.add_argument("--semilla",  type=int,   default=42,
                        help="Semilla aleatoria (default: 42)")
    parser.add_argument("--pct",      type=float, default=0.12,
                        help="Porcentaje de relleno inicial (default: 0.12)")
    parser.add_argument("--max_nodos", type=int,  default=150_000,
                        help="Máximo de nodos (default: 150000)")
    parser.add_argument("--max_tiempo", type=int, default=120,
                        help="Tiempo máximo en segundos (default: 90)")
    parser.add_argument("--delay",    type=float, default=0.08,
                        help="Delay inicial de animación en seg (default: 0.08)")
    args = parser.parse_args()

    print("="*55)
    print("  SUDOKU 9 TABLEROS — Visualizador A*")
    print("="*55)
    print(f"  Semilla          : {args.semilla}")
    print(f"  Relleno inicial  : {args.pct*100:.0f}%")
    print(f"  Límite nodos     : {args.max_nodos:,}")
    print(f"  Límite tiempo    : {args.max_tiempo}s")

    # ── generar estado inicial ────────────────────────────────────────────
    print("\n[1/3] Generando estado inicial aleatorio...")
    estado_inicial, celdas_fijas = generar_estado_aleatorio(
        porcentaje_relleno=args.pct,
        semilla=args.semilla,
    )

    if not estado_inicial.es_consistente():
        print("\n[ERROR] Estado inicial INCONSISTENTE — sin solución.")
        sys.exit(1)

    n_fijas = sum(1 for z in range(9) for x in range(9)
                  for y in range(9) if estado_inicial.grid[z][x][y] != 0)
    print(f"         Celdas prellenadas: {n_fijas} / 729")

    # ── ejecutar A* ───────────────────────────────────────────────────────
    print("\n[2/3] Ejecutando A*...")
    t0 = time.time()
    arbol = ArbolBuscadorAStar(
        estado_inicial,
        max_nodos=args.max_nodos,
        max_tiempo=args.max_tiempo,
    )
    solucion, ruta, es_optima = arbol.buscar()
    elapsed = time.time() - t0

    if not solucion:
        print("\n[ERROR] No se encontró solución.")
        sys.exit(1)

    if not ruta:
        print("\n[INFO] El estado inicial ya era la solución (sin pasos).")

    beff = ArbolBuscadorAStar._factor_ramificacion_efectivo(
        len(ruta), arbol.nodos_cerrados
    ) if ruta else 0.0

    stats = {
        "abiertos"  : arbol.nodos_abiertos,
        "cerrados"  : arbol.nodos_cerrados,
        "backtracks": arbol.backtracks,
        "tiempo"    : f"{elapsed:.1f}",
        "beff"      : f"{beff:.4f}",
    }

    print(f"\n  Ruta encontrada: {len(ruta)} pasos")
    print(f"  Nodos cerrados : {arbol.nodos_cerrados:,}")
    print(f"  b* efectivo    : {beff:.4f}")

    # ── lanzar visualizador ───────────────────────────────────────────────
    print("\n[3/3] Abriendo visualizador...\n")
    print("  Controles:")
    print("    ▶ Play   — reproduce automáticamente")
    print("    ◀ Prev / Next ▶ — paso a paso")
    print("    ↺ Reset  — vuelve al inicio")
    print("    Slider   — velocidad de reproducción")

    viz = Visualizador(
        estado_inicial=estado_inicial,
        celdas_fijas=celdas_fijas,
        ruta=ruta,
        estado_resuelto=solucion,
        stats=stats,
    )
    viz.delay = args.delay
    viz.mostrar()


if __name__ == "__main__":
    main()