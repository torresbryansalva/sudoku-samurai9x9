"""
main2.py  —  Visualizador paso a paso del Sudoku 9 Tableros (Pygame)
====================================================================
Variante de main.py que usa DFS + Backtracking + MRV en lugar de A*.

Importa sudoku2.py como backend y muestra con pygame:
  - Layout de los 9 tableros (posicion fiel al dibujo original)
  - Animacion celda por celda de la ruta de solucion
  - Panel de estadisticas en tiempo real
  - Barra de progreso y controles de velocidad
  - Botones Play / Pausa / Prev / Next / Reset

Uso:
    python main2.py
    python main2.py --semilla 7 --pct 0.12 --delay 0.3
"""

import sys
import os
import copy
import argparse
import time

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import pygame

from utils.sudoku2 import (
    generar_estado_aleatorio,
    ArbolBuscadorDFS,
    CONEXIONES,
)


# ============================================================================
# LAYOUT 5x5 — posicion de cada tablero (fiel al diseno original)
# ============================================================================

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


# ============================================================================
# COLORES (RGB)
# ============================================================================

COLOR_FIJO      = (96, 34, 138)
COLOR_NUEVO     = (233, 69, 96)
COLOR_ESPEJO    = (245, 166, 35)
COLOR_NORMAL    = (29, 85, 138)
COLOR_VACIO     = (142, 167, 197)
COLOR_BG        = (62, 197, 141)
COLOR_PANEL_BG  = (13, 13, 31)
COLOR_TEXT      = (224, 224, 255)
COLOR_TEXT_NEW  = (255, 255, 255)
COLOR_BORDER    = (83, 216, 251)
COLOR_GRID_LINE = (42, 42, 74)
COLOR_BTN_BG    = (26, 26, 58)
COLOR_BTN_HOV   = (233, 69, 96)
COLOR_BTN_PLAY  = (26, 95, 55)
COLOR_PROG_OK   = (0, 255, 136)
COLOR_PROG_PART = (245, 166, 35)

# ============================================================================
# DIMENSIONES
# ============================================================================

WINDOW_W = 1400
WINDOW_H = 820

BOARD_AREA_X = 10
BOARD_AREA_Y = 50
BOARD_AREA_W = 980
BOARD_AREA_H = 680

PANEL_X = 1000
PANEL_Y = 50
PANEL_W = 390
PANEL_H = 680

CTRL_Y = 760
CTRL_H = 45


# ============================================================================
# UTILIDADES DE DIBUJO
# ============================================================================

class Button:
    def __init__(self, rect, label, color=COLOR_BTN_BG, hover=COLOR_BTN_HOV):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color = color
        self.hover = hover
        self.is_hover = False

    def draw(self, surf, font):
        c = self.hover if self.is_hover else self.color
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, COLOR_BORDER, self.rect, 1, border_radius=6)
        txt = font.render(self.label, True, (255, 255, 255))
        tx = self.rect.centerx - txt.get_width() // 2
        ty = self.rect.centery - txt.get_height() // 2
        surf.blit(txt, (tx, ty))

    def handle_motion(self, pos):
        self.is_hover = self.rect.collidepoint(pos)

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


class Slider:
    def __init__(self, rect, vmin, vmax, vinit, label="Velocidad"):
        self.rect = pygame.Rect(rect)
        self.vmin = vmin
        self.vmax = vmax
        self.value = vinit
        self.label = label
        self.dragging = False

    def _val_to_x(self):
        pct = (self.value - self.vmin) / (self.vmax - self.vmin)
        return int(self.rect.x + pct * self.rect.w)

    def _x_to_val(self, x):
        pct = max(0.0, min(1.0, (x - self.rect.x) / self.rect.w))
        return self.vmin + pct * (self.vmax - self.vmin)

    def draw(self, surf, font):
        track = pygame.Rect(self.rect.x, self.rect.centery - 3,
                            self.rect.w, 6)
        pygame.draw.rect(surf, COLOR_BTN_BG, track, border_radius=3)
        pygame.draw.rect(surf, COLOR_BORDER, track, 1, border_radius=3)
        fx = self._val_to_x()
        filled = pygame.Rect(self.rect.x, self.rect.centery - 3,
                             fx - self.rect.x, 6)
        pygame.draw.rect(surf, COLOR_BORDER, filled, border_radius=3)
        pygame.draw.circle(surf, (255, 255, 255), (fx, self.rect.centery), 8)
        pygame.draw.circle(surf, COLOR_BORDER, (fx, self.rect.centery), 8, 2)
        txt = font.render(f"{self.label}: {self.value:.2f}s",
                          True, (255, 255, 255))
        surf.blit(txt, (self.rect.x, self.rect.y - 20))

    def handle_down(self, pos):
        if self.rect.collidepoint(pos) or \
                pygame.Rect(self.rect.x, self.rect.y - 8,
                            self.rect.w, self.rect.h + 16).collidepoint(pos):
            self.dragging = True
            self.value = self._x_to_val(pos[0])
            return True
        return False

    def handle_up(self):
        self.dragging = False

    def handle_motion(self, pos):
        if self.dragging:
            self.value = self._x_to_val(pos[0])


# ============================================================================
# VISUALIZADOR PRINCIPAL (Pygame)
# ============================================================================

class Visualizador:

    def __init__(self, estado_inicial, celdas_fijas,
                 ruta, estado_resuelto, stats, es_optima=True):

        self.estado_inicial  = estado_inicial
        self.estado_resuelto = estado_resuelto
        self.ruta            = ruta
        self.stats           = stats
        self.es_optima       = es_optima
        self.paso_actual     = 0
        self.total_pasos     = len(ruta)
        self.reproduciendo   = False
        self.delay           = 0.3
        self._t_ultimo_step  = 0.0

        self.fijas = {z: set() for z in range(9)}
        for (z, x, y) in celdas_fijas:
            self.fijas[z].add((x, y))

        self.grid_actual = copy.deepcopy(estado_inicial.grid)

        self._calcular_geometria()

    def _calcular_geometria(self):
        gap = 6
        cell_w = (BOARD_AREA_W - gap * 6) // 5
        cell_h = (BOARD_AREA_H - gap * 6) // 5
        self.board_size = min(cell_w, cell_h)
        self.cell_size = self.board_size // 9

        self.board_rects = {}
        grid_total_w = 5 * self.board_size + 4 * gap
        grid_total_h = 5 * self.board_size + 4 * gap
        ox = BOARD_AREA_X + (BOARD_AREA_W - grid_total_w) // 2
        oy = BOARD_AREA_Y + (BOARD_AREA_H - grid_total_h) // 2

        for z, (row, col) in GRID_POS.items():
            bx = ox + col * (self.board_size + gap)
            by = oy + row * (self.board_size + gap)
            self.board_rects[z] = pygame.Rect(
                bx, by, self.board_size, self.board_size
            )

    def _init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        title = "Sudoku 9 Tableros - Visualizador DFS+MRV"
        if not self.es_optima:
            title += "  [SOLUCION PARCIAL]"
        pygame.display.set_caption(title)

        self.clock = pygame.time.Clock()

        self.font_cell  = pygame.font.SysFont("consolas", max(10, self.cell_size - 6), bold=True)
        self.font_small = pygame.font.SysFont("consolas", 12)
        self.font_med   = pygame.font.SysFont("consolas", 14)
        self.font_big   = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_btn   = pygame.font.SysFont("consolas", 14, bold=True)

        self._construir_controles()

    def _construir_controles(self):
        y = CTRL_Y
        h = 36
        self.btn_prev = Button((20, y, 90, h), "< Prev")
        self.btn_play = Button((120, y, 130, h), "> DALE PLAY",
                               color=COLOR_BTN_PLAY)
        self.btn_next = Button((260, y, 90, h), "Next >")
        self.btn_reset = Button((360, y, 90, h), "Reset")
        self.slider = Slider((480, y + 14, 280, h - 28),
                             0.05, 1.0, self.delay, "Velocidad")
        self.buttons = [self.btn_prev, self.btn_play,
                        self.btn_next, self.btn_reset]

    def _aplicar_paso(self, n):
        self.grid_actual = copy.deepcopy(self.estado_inicial.grid)
        for i in range(n):
            z, x, y, v = self.ruta[i]["operador"]
            self.grid_actual[z][x][y] = v
            if (z, x, y) in CONEXIONES:
                for (ze, xe, ye) in CONEXIONES[(z, x, y)]:
                    self.grid_actual[ze][xe][ye] = v

    def _espejos_de_op(self, op):
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

    def _dibujar_tablero(self, z, ultimo=None, espejos=None):
        rect = self.board_rects[z]
        espejos = espejos or set()
        grid = self.grid_actual[z]
        fijas = self.fijas[z]

        pygame.draw.rect(self.screen, COLOR_BG, rect)

        cs = self.cell_size
        ox = rect.x + (rect.w - cs * 9) // 2
        oy = rect.y + (rect.h - cs * 9) // 2

        for x in range(9):
            for y in range(9):
                val = grid[x][y]
                celda = (x, y)

                if celda == ultimo:
                    bg = COLOR_NUEVO
                elif celda in espejos:
                    bg = COLOR_ESPEJO
                elif celda in fijas:
                    bg = COLOR_FIJO
                elif val != 0:
                    bg = COLOR_NORMAL
                else:
                    bg = COLOR_VACIO

                cx = ox + y * cs
                cy = oy + x * cs
                cell_rect = pygame.Rect(cx + 1, cy + 1, cs - 2, cs - 2)
                pygame.draw.rect(self.screen, bg, cell_rect, border_radius=3)

                if val != 0:
                    color_txt = COLOR_TEXT_NEW if (
                        celda == ultimo or celda in espejos
                    ) else COLOR_TEXT
                    txt = self.font_cell.render(str(val), True, color_txt)
                    tx = cx + cs // 2 - txt.get_width() // 2
                    ty = cy + cs // 2 - txt.get_height() // 2
                    self.screen.blit(txt, (tx, ty))

        for k in range(10):
            if k % 3 != 0:
                pygame.draw.line(self.screen, COLOR_GRID_LINE,
                                 (ox + k * cs, oy),
                                 (ox + k * cs, oy + 9 * cs), 1)
                pygame.draw.line(self.screen, COLOR_GRID_LINE,
                                 (ox, oy + k * cs),
                                 (ox + 9 * cs, oy + k * cs), 1)
        for k in range(0, 10, 3):
            pygame.draw.line(self.screen, COLOR_BORDER,
                             (ox + k * cs, oy),
                             (ox + k * cs, oy + 9 * cs), 2)
            pygame.draw.line(self.screen, COLOR_BORDER,
                             (ox, oy + k * cs),
                             (ox + 9 * cs, oy + k * cs), 2)

        title = self.font_small.render(f"Tablero {z}", True, COLOR_BORDER)
        self.screen.blit(title, (rect.x + 4, rect.y + 2))

    def _dibujar_panel_info(self, ultimo_op=None):
        info_rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, 380)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG,
                         info_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_BORDER,
                         info_rect, 2, border_radius=8)

        x = PANEL_X + 16
        y = PANEL_Y + 12

        t = self.font_big.render("ESTADISTICAS DFS", True, COLOR_BORDER)
        self.screen.blit(t, (x, y))
        y += 30

        if not self.es_optima:
            warn = self.font_med.render("!! SOLUCION PARCIAL !!",
                                        True, COLOR_NUEVO)
            self.screen.blit(warn, (x, y)); y += 18
            for line in ("Limite de busqueda", "alcanzado. Celdas",
                         "sin resolver."):
                t = self.font_small.render(line, True, COLOR_PROG_PART)
                self.screen.blit(t, (x, y)); y += 14
            y += 8

        vacias = sum(
            1 for z in range(9)
            for xx in range(9)
            for yy in range(9)
            if self.grid_actual[z][xx][yy] == 0
        )
        llenadas = 729 - vacias

        lines = [
            (f"Paso          {self.paso_actual} / {self.total_pasos}",
             COLOR_TEXT_NEW),
            (f"Celdas llenas {llenadas} / 729", COLOR_BORDER),
            (f"Celdas vacias {vacias}", (170, 170, 204)),
            ("", COLOR_TEXT_NEW),
            (f"Nodos pila    {self.stats.get('abiertos', '?')}",
             COLOR_TEXT_NEW),
            (f"Nodos cerrados {self.stats.get('cerrados', '?')}",
             COLOR_TEXT_NEW),
            (f"Backtracks     {self.stats.get('backtracks', '?')}",
             COLOR_PROG_PART),
            (f"Profundidad mx {self.stats.get('prof_max', '?')}",
             COLOR_TEXT_NEW),
            (f"Tiempo busq.   {self.stats.get('tiempo', '?')}s",
             COLOR_TEXT_NEW),
            (f"b* efectivo    {self.stats.get('beff', '?')}",
             COLOR_NUEVO),
        ]
        for text, color in lines:
            t = self.font_med.render(text, True, color)
            self.screen.blit(t, (x, y))
            y += 18

        if ultimo_op:
            y += 6
            t = self.font_med.render("ULTIMO OPERADOR", True, COLOR_BORDER)
            self.screen.blit(t, (x, y)); y += 18
            z, xx, yy, v = ultimo_op
            t = self.font_small.render(
                f"Tablero {z}  fila {xx}  col {yy}",
                True, COLOR_PROG_PART)
            self.screen.blit(t, (x, y)); y += 16
            t = self.font_big.render(f"-> valor {v}", True, COLOR_NUEVO)
            self.screen.blit(t, (x, y)); y += 22

    def _dibujar_progreso(self):
        bar_x = PANEL_X + 16
        bar_y = PANEL_Y + 400
        bar_w = PANEL_W - 32
        bar_h = 22

        pct = self.paso_actual / max(self.total_pasos, 1)
        color_full = COLOR_PROG_PART if not self.es_optima else COLOR_PROG_OK
        label_suffix = " (PARCIAL)" if not self.es_optima else ""

        bg_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(self.screen, COLOR_BTN_BG,
                         bg_rect, border_radius=6)
        pygame.draw.rect(self.screen, COLOR_BORDER,
                         bg_rect, 1, border_radius=6)

        if pct > 0:
            fill_w = max(2, int(bar_w * pct))
            fill_rect = pygame.Rect(bar_x, bar_y, fill_w, bar_h)
            fill_color = color_full if pct >= 1.0 else COLOR_NUEVO
            pygame.draw.rect(self.screen, fill_color,
                             fill_rect, border_radius=6)

        txt = self.font_med.render(
            f"{pct * 100:.1f}%  completado{label_suffix}",
            True, (255, 255, 255))
        self.screen.blit(
            txt,
            (bar_x + bar_w // 2 - txt.get_width() // 2, bar_y - 20)
        )

    def _dibujar_leyenda(self):
        x = PANEL_X + 16
        y = PANEL_Y + 460
        w = PANEL_W - 32
        h = 200

        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_BORDER, rect, 2, border_radius=8)

        t = self.font_big.render("LEYENDA", True, COLOR_BORDER)
        self.screen.blit(t, (x + 12, y + 8))

        items = [
            (COLOR_FIJO,   "Celda inicial (fija)"),
            (COLOR_NUEVO,  "Ultimo valor colocado"),
            (COLOR_ESPEJO, "Espejo propagado"),
            (COLOR_NORMAL, "Valor resuelto"),
            (COLOR_VACIO,  "Celda vacia"),
        ]
        yy = y + 40
        for color, label in items:
            sw_rect = pygame.Rect(x + 16, yy + 2, 22, 18)
            pygame.draw.rect(self.screen, color, sw_rect, border_radius=4)
            pygame.draw.rect(self.screen, (51, 51, 85),
                             sw_rect, 1, border_radius=4)
            t = self.font_med.render(label, True, (255, 255, 255))
            self.screen.blit(t, (x + 48, yy + 2))
            yy += 28

    def _dibujar_controles(self):
        for b in self.buttons:
            b.draw(self.screen, self.font_btn)
        self.slider.draw(self.screen, self.font_small)

        info = self.font_med.render(
            f"Paso  {self.paso_actual} / {self.total_pasos}",
            True, (255, 255, 255))
        self.screen.blit(info, (790, CTRL_Y + 10))

    def _dibujar_titulo(self):
        title = "SUDOKU 9 TABLEROS  -  Busqueda DFS + Backtracking + MRV"
        if not self.es_optima:
            title += "  (solucion parcial)"
        t = self.font_title.render(title, True, COLOR_BORDER)
        self.screen.blit(
            t, (WINDOW_W // 2 - t.get_width() // 2, 10)
        )

    def _dibujar_frame(self):
        self.screen.fill(COLOR_BG)

        if self.paso_actual > 0:
            op = self.ruta[self.paso_actual - 1]["operador"]
        else:
            op = None
        espejos_op = self._espejos_de_op(op)

        pygame.draw.rect(self.screen, COLOR_PANEL_BG,
                         (0, 0, WINDOW_W, 40))
        self._dibujar_titulo()

        for z in range(9):
            ult = None
            if op and op[0] == z:
                ult = (op[1], op[2])
            self._dibujar_tablero(
                z,
                ultimo=ult,
                espejos=espejos_op.get(z, set()),
            )

        self._dibujar_panel_info(ultimo_op=op)
        self._dibujar_progreso()
        self._dibujar_leyenda()

        pygame.draw.rect(self.screen, COLOR_PANEL_BG,
                         (0, CTRL_Y - 10, WINDOW_W, CTRL_H + 30))
        self._dibujar_controles()

        pygame.display.flip()

    def _on_play(self):
        if self.paso_actual >= self.total_pasos:
            self.paso_actual = 0
            self._aplicar_paso(0)
        self.reproduciendo = not self.reproduciendo
        self.btn_play.label = "|| Pausa" if self.reproduciendo else "> Play"
        self._t_ultimo_step = time.time()

    def _on_prev(self):
        self.reproduciendo = False
        self.btn_play.label = "> Play"
        self._ir_a_paso(self.paso_actual - 1)

    def _on_next(self):
        self.reproduciendo = False
        self.btn_play.label = "> Play"
        self._ir_a_paso(self.paso_actual + 1)

    def _on_reset(self):
        self.reproduciendo = False
        self.btn_play.label = "> Play"
        self._ir_a_paso(0)

    def _handle_event(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            elif ev.key == pygame.K_SPACE:
                self._on_play()
            elif ev.key in (pygame.K_RIGHT, pygame.K_n):
                self._on_next()
            elif ev.key in (pygame.K_LEFT, pygame.K_p):
                self._on_prev()
            elif ev.key == pygame.K_r:
                self._on_reset()
        elif ev.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.handle_motion(ev.pos)
            self.slider.handle_motion(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.btn_play.clicked(ev.pos):
                self._on_play()
            elif self.btn_prev.clicked(ev.pos):
                self._on_prev()
            elif self.btn_next.clicked(ev.pos):
                self._on_next()
            elif self.btn_reset.clicked(ev.pos):
                self._on_reset()
            else:
                self.slider.handle_down(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.slider.handle_up()
        return True

    def mostrar(self):
        self._init_pygame()
        self._t_ultimo_step = time.time()
        corriendo = True
        while corriendo:
            for ev in pygame.event.get():
                if not self._handle_event(ev):
                    corriendo = False
                    break

            self.delay = self.slider.value

            if self.reproduciendo:
                ahora = time.time()
                if ahora - self._t_ultimo_step >= self.delay:
                    if self.paso_actual < self.total_pasos:
                        self._ir_a_paso(self.paso_actual + 1)
                        self._t_ultimo_step = ahora
                    else:
                        self.reproduciendo = False
                        self.btn_play.label = "> Play"

            self._dibujar_frame()
            self.clock.tick(60)

        pygame.quit()


# ============================================================================
# MAIN
# ============================================================================

def main():
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(
        description="Visualizador paso a paso del Sudoku 9 Tableros con DFS+MRV (pygame)"
    )
    parser.add_argument("--semilla",   type=int,   default=42)
    parser.add_argument("--pct",       type=float, default=0.12)
    parser.add_argument("--max_nodos", type=int,   default=2_000_000)
    parser.add_argument("--max_tiempo",type=int,   default=180)
    parser.add_argument("--delay",     type=float, default=0.3)
    args = parser.parse_args()

    print("=" * 55, flush=True)
    print("  SUDOKU 9 TABLEROS - Visualizador DFS+MRV (pygame)", flush=True)
    print("=" * 55, flush=True)
    print(f"  Semilla          : {args.semilla}", flush=True)
    print(f"  Relleno inicial  : {args.pct * 100:.0f}%", flush=True)
    print(f"  Limite nodos     : {args.max_nodos:,}", flush=True)
    print(f"  Limite tiempo    : {args.max_tiempo}s", flush=True)

    print("\n[1/3] Generando estado inicial aleatorio...", flush=True)
    estado_inicial, celdas_fijas = generar_estado_aleatorio(
        porcentaje_relleno=args.pct,
        semilla=args.semilla,
    )

    if not estado_inicial.es_consistente():
        print("\n[ERROR] Estado inicial INCONSISTENTE.", flush=True)
        sys.exit(1)

    n_fijas = sum(
        1 for z in range(9) for x in range(9) for y in range(9)
        if estado_inicial.grid[z][x][y] != 0
    )
    print(f"         Celdas prellenadas: {n_fijas} / 729", flush=True)

    print("\n[2/3] Ejecutando DFS + Backtracking + MRV...", flush=True)
    t0 = time.time()
    arbol = ArbolBuscadorDFS(
        estado_inicial,
        max_nodos=args.max_nodos,
        max_tiempo=args.max_tiempo,
    )
    solucion, ruta, es_optima = arbol.buscar()
    elapsed = time.time() - t0

    if not solucion:
        print("\n[ERROR] No se encontro solucion.", flush=True)
        sys.exit(1)

    if not ruta:
        print("\n[INFO] El estado inicial ya era la solucion.", flush=True)

    beff = ArbolBuscadorDFS._factor_ramificacion_efectivo(
        len(ruta), arbol.nodos_cerrados
    ) if ruta else 0.0

    stats = {
        "abiertos"  : arbol.nodos_abiertos,
        "cerrados"  : arbol.nodos_cerrados,
        "backtracks": arbol.backtracks,
        "prof_max"  : arbol.profundidad_max_alcanzada,
        "tiempo"    : f"{elapsed:.1f}",
        "beff"      : f"{beff:.4f}",
    }

    print(f"\n  Ruta encontrada: {len(ruta)} pasos", flush=True)
    print(f"  Nodos cerrados : {arbol.nodos_cerrados:,}", flush=True)
    print(f"  Backtracks     : {arbol.backtracks:,}", flush=True)
    print(f"  Profundidad max: {arbol.profundidad_max_alcanzada}", flush=True)
    print(f"  b* efectivo    : {beff:.4f}", flush=True)

    print("\n[3/3] Abriendo visualizador (pygame)...\n", flush=True)
    print("  Controles:", flush=True)
    print("    Mouse  ->  botones / slider", flush=True)
    print("    Espacio -> Play / Pausa", flush=True)
    print("    Flecha derecha / N -> siguiente paso", flush=True)
    print("    Flecha izquierda / P -> paso anterior", flush=True)
    print("    R -> Reset", flush=True)
    print("    Esc -> Salir", flush=True)

    viz = Visualizador(
        estado_inicial=estado_inicial,
        celdas_fijas=celdas_fijas,
        ruta=ruta,
        estado_resuelto=solucion,
        stats=stats,
        es_optima=es_optima,
    )
    viz.delay = args.delay
    viz.mostrar()


if __name__ == "__main__":
    main()
