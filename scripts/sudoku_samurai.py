"""
==============================================================================
SUDOKU 9x9 - BÚSQUEDA EN ESPACIO DE ESTADOS CON A*
MIA-103 Fundamentos de Inteligencia Artificial - Examen Parcial
==============================================================================

Problema 4.5 del Anexo 1 (tablero individual 9x9 como el mostrado en el PDF).

Componentes (siguiendo la sección 2 del PDF):
  - 2.4  Estado y sus métodos     -> clase SudokuState
  - 2.5  Nodo y sus métodos       -> clase Node
  - 2.6  Árbol y sus métodos      -> clase SearchTree (lista abierta/cerrada,
                                                       criterios de terminación)
  - 2.7  Pruebas                  -> función main() con caso aleatorio 15%
  - 2.8  Análisis                 -> estadísticas finales y mejor solución parcial

Algoritmo: A*
  - g(n)  = profundidad del nodo (número de celdas llenadas desde el inicial)
  - h(n)  = número de celdas vacías restantes (admisible y exacta cuando el
            problema es soluble; +infinito si detecta estado muerto)
  - f(n)  = g(n) + h(n)
"""

import numpy as np
import random
import heapq
import time

# ============================================================================
# CONSTANTES
# ============================================================================
N      = 9        # tamaño del tablero (9x9)
BOX    = 3        # tamaño de cada bloque (3x3)
EMPTY  = 0        # marca de celda vacía
DIGITS = set(range(1, 10))


# ============================================================================
# 1.  ESTADO DEL PROBLEMA   (sección 2.4 del PDF)
# ============================================================================
class SudokuState:
    """
    Ontología del Sudoku 9x9:

      Atributos
      ---------
      grid : np.ndarray (9,9)  valores en {0, 1..9}
             0   = celda vacía por llenar
             1-9 = dígito asignado

      Métodos principales
      -------------------
      - is_goal()                : prueba de meta
      - successors()             : función sucesora (operadores aplicables)
      - get_possible_values(r,c) : valores admisibles para una celda
      - fill_percentage()        : % de llenado del estado

    Restricciones del problema (PDF §4.5):
      * cada fila debe contener los dígitos 1..9 sin repetir
      * cada columna debe contener los dígitos 1..9 sin repetir
      * cada bloque 3x3 debe contener los dígitos 1..9 sin repetir
    """

    def __init__(self, grid=None):
        if grid is None:
            self.grid = np.zeros((N, N), dtype=np.int8)
        else:
            self.grid = grid

    # ------------------------------------------------------------------
    # Restricciones: dada una celda, ¿qué celdas comparten restricción?
    # ------------------------------------------------------------------
    def get_possible_values(self, r, c):
        """Conjunto de dígitos legales para la celda (r,c)."""
        if self.grid[r, c] != EMPTY:
            return set()
        used = set()
        # fila completa
        for cc in range(N):
            v = self.grid[r, cc]
            if v > 0:
                used.add(int(v))
        # columna completa
        for rr in range(N):
            v = self.grid[rr, c]
            if v > 0:
                used.add(int(v))
        # bloque 3x3
        br = (r // BOX) * BOX
        bc = (c // BOX) * BOX
        for rr in range(br, br + BOX):
            for cc in range(bc, bc + BOX):
                v = self.grid[rr, cc]
                if v > 0:
                    used.add(int(v))
        return DIGITS - used

    # ------------------------------------------------------------------
    # Conteos útiles
    # ------------------------------------------------------------------
    def filled_count(self):
        return int(np.sum(self.grid > 0))

    def empty_cells(self):
        rs, cs = np.where(self.grid == EMPTY)
        return list(zip(rs.tolist(), cs.tolist()))

    def fill_percentage(self):
        return 100.0 * self.filled_count() / (N * N)

    # ------------------------------------------------------------------
    # Prueba de meta y función sucesora
    # ------------------------------------------------------------------
    def is_goal(self):
        """Meta: no quedan celdas vacías (el tablero está completo)."""
        return not np.any(self.grid == EMPTY)

    def successors(self):
        """
        Función sucesora con heurística MRV (Minimum Remaining Values):
        en lugar de generar |empty| * 9 hijos, elegimos UNA celda
        (la más restringida) y generamos un hijo por cada valor legal.
        Esto reduce drásticamente el factor de ramificación efectivo.

        Devuelve lista de tuplas: (estado_hijo, operador, costo)
            operador = (r, c, v)  significa "asignar v a la celda (r,c)"
            costo    = 1 (uniforme)
        """
        empties = self.empty_cells()
        if not empties:
            return []

        best_cell, best_vals = None, None
        best_n = 10
        for r, c in empties:
            vals = self.get_possible_values(r, c)
            if len(vals) < best_n:
                best_n  = len(vals)
                best_cell = (r, c)
                best_vals = vals
                if best_n == 0:
                    return []        # estado muerto: sin sucesores
                if best_n == 1:
                    break            # cell forced

        succs = []
        r, c = best_cell
        for v in sorted(best_vals):
            new_grid = self.grid.copy()
            new_grid[r, c] = v
            succs.append((SudokuState(new_grid), (r, c, v), 1))
        return succs

    # ------------------------------------------------------------------
    # Hash, igualdad, impresión
    # ------------------------------------------------------------------
    def __hash__(self):
        return hash(self.grid.tobytes())

    def __eq__(self, other):
        return isinstance(other, SudokuState) and np.array_equal(self.grid, other.grid)

    def display(self):
        """Imprime el tablero 9x9 con separadores 3x3."""
        out = []
        for r in range(N):
            if r % BOX == 0 and r > 0:
                out.append('-' * 25)
            row = []
            for c in range(N):
                if c % BOX == 0 and c > 0:
                    row.append('|')
                v = self.grid[r, c]
                row.append('.' if v == EMPTY else str(int(v)))
            out.append(' '.join(row))
        return '\n'.join(out)


# ============================================================================
# 2.  NODO DEL ÁRBOL DE BÚSQUEDA   (sección 2.5 del PDF)
# ============================================================================
class Node:
    """
    Nodo del árbol de búsqueda.
    Un nodo CONTIENE un estado pero no es un estado.

    Atributos propios del nodo (independientes del estado):
      - parent     : nodo padre (None si es la raíz)
      - operator   : operador aplicado al padre para generar este nodo (r,c,v)
      - g          : costo acumulado desde la raíz
      - h          : valor de la heurística
      - f          : g + h
      - depth      : profundidad en el árbol
      - id         : identificador único (orden de creación)
    """
    _counter = 0

    def __init__(self, state, parent=None, operator=None, g=0, h=0):
        self.state    = state
        self.parent   = parent
        self.operator = operator
        self.g        = g
        self.h        = h
        self.f        = g + h
        self.depth    = 0 if parent is None else parent.depth + 1
        Node._counter += 1
        self.id = Node._counter

    def path(self):
        """Reconstruye la ruta raíz -> este nodo."""
        seq, n = [], self
        while n is not None:
            seq.append(n)
            n = n.parent
        return list(reversed(seq))

    def __lt__(self, other):
        return self.id < other.id


# ============================================================================
# 3.  HEURÍSTICA  -  h(n)
# ============================================================================
def heuristic(state):
    """
    h(n) = número de celdas vacías que faltan por llenar.

    ADMISIBLE: cada operador llena exactamente UNA celda, por lo que
    se necesitan al menos |vacías| pasos para alcanzar la meta.
    De hecho es EXACTA cuando el problema es soluble desde n.

    Si alguna celda vacía no tiene ningún valor legal => estado muerto
    => h = +infinito (A* lo evita).
    """
    empties = state.empty_cells()
    h = len(empties)
    for r, c in empties:
        if not state.get_possible_values(r, c):
            return float('inf')
    return h


# ============================================================================
# 4.  ÁRBOL DE BÚSQUEDA Y ALGORITMO A*   (sección 2.6 del PDF)
# ============================================================================
class SearchTree:
    """
    Árbol de búsqueda con A*.

    Estructuras:
      - open_heap : cola de prioridad (frontera) ordenada por (f, -depth, id)
      - closed    : conjunto de estados ya expandidos

    Criterios de terminación (PDF 2.6):
      - max_nodes   : tope de nodos expandidos
      - max_depth   : profundidad máxima
      - max_time    : tiempo máximo en segundos

    Si se cumple alguno, el algoritmo devuelve el MEJOR nodo parcial
    encontrado (el de mayor % de llenado).
    """

    def __init__(self, initial_state,
                 max_nodes=200000, max_depth=10**9, max_time=30.0,
                 verbose=True, log_every=200):
        self.initial      = initial_state
        self.max_nodes    = max_nodes
        self.max_depth    = max_depth
        self.max_time     = max_time
        self.verbose      = verbose
        self.log_every    = log_every

        # listas requeridas por el PDF
        self.open_heap    = []      # nodos abiertos (frontera)
        self.closed       = set()   # nodos cerrados (estados ya expandidos)

        # estadísticas
        self.nodes_expanded   = 0
        self.nodes_generated  = 0
        self.elapsed          = 0.0

    # ------------------------------------------------------------------
    def a_star(self):
        """Ejecuta A* y devuelve (solucion, mejor_parcial, stats)."""
        Node._counter = 0
        t0 = time.time()

        h0   = heuristic(self.initial)
        root = Node(self.initial, g=0, h=h0)
        self.nodes_generated = 1
        heapq.heappush(self.open_heap, (root.f, -root.depth, root.id, root))

        best_partial = root

        if self.verbose:
            print(f"\n--- INICIO A* ---")
            print(f"Estado inicial: llenado={self.initial.fill_percentage():.1f}%, "
                  f"vacías={h0}")
            print(f"g(s0)=0  h(s0)={h0}  f(s0)={h0}\n")

        while self.open_heap:
            self.elapsed = time.time() - t0
            if self.elapsed > self.max_time:
                if self.verbose:
                    print(f"\n[STOP] Tiempo máximo alcanzado ({self.max_time}s)")
                break
            if self.nodes_expanded >= self.max_nodes:
                if self.verbose:
                    print(f"\n[STOP] Máximo de nodos expandidos ({self.max_nodes})")
                break

            f, _, _, node = heapq.heappop(self.open_heap)

            if node.state in self.closed:
                continue
            self.closed.add(node.state)
            self.nodes_expanded += 1

            if node.depth > self.max_depth:
                continue

            # registro del MEJOR parcial (mayor % de llenado)
            if node.state.fill_percentage() > best_partial.state.fill_percentage():
                best_partial = node

            # log de progreso
            if self.verbose and self.nodes_expanded % self.log_every == 0:
                print(f"  [exp={self.nodes_expanded:5d}] "
                      f"depth={node.depth:2d} g={node.g:2d} h={node.h:2d} "
                      f"f={node.f:2d} fill={node.state.fill_percentage():5.1f}% "
                      f"frontera={len(self.open_heap)}")

            # PRUEBA DE META
            if node.state.is_goal():
                self.elapsed = time.time() - t0
                if self.verbose:
                    print(f"\n*** SOLUCIÓN COMPLETA EN NODO #{self.nodes_expanded} ***")
                    print(f"    g={node.g} h={node.h} f={node.f} depth={node.depth}")
                return node, node, self._stats(True)

            # EXPANSIÓN
            for child_state, op, cost in node.state.successors():
                if child_state in self.closed:
                    continue
                ng = node.g + cost
                nh = heuristic(child_state)
                child = Node(child_state, parent=node, operator=op, g=ng, h=nh)
                self.nodes_generated += 1
                heapq.heappush(self.open_heap,
                               (child.f, -child.depth, child.id, child))

        # se agotó la frontera o algún criterio de parada
        self.elapsed = time.time() - t0
        if self.verbose:
            print(f"\n[FIN] Sin solución completa.")
            print(f"      Mejor parcial: {best_partial.state.fill_percentage():.1f}% "
                  f"(depth={best_partial.depth})")
        return None, best_partial, self._stats(False)

    # ------------------------------------------------------------------
    def _stats(self, solved):
        b_eff = (self.nodes_generated / self.nodes_expanded
                 if self.nodes_expanded > 0 else 0)
        return {
            'expanded'           : self.nodes_expanded,
            'generated'          : self.nodes_generated,
            'frontier_remaining' : len(self.open_heap),
            'time_s'             : self.elapsed,
            'branching_eff'      : b_eff,
            'solved'             : solved,
        }


# ============================================================================
# 5.  GENERACIÓN DEL ESTADO INICIAL ALEATORIO (15% lleno = ~12 celdas)
# ============================================================================
def random_initial_state(fill_pct=15, seed=None):
    """
    Construye un estado inicial llenando aleatoriamente celdas con valores
    legales hasta alcanzar el % objetivo.

    Como las asignaciones son consistentes en cada paso, NO se garantiza
    que el problema sea soluble globalmente (el PDF lo permite: el agente
    debe poder identificar problemas sin solución).

    Con 15% de 81 celdas = ~12 celdas, está por debajo del mínimo de 17
    pistas que la teoría exige para unicidad de solución; por lo tanto
    el problema usualmente tendrá MÚLTIPLES soluciones (A* encontrará
    una de ellas).
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    s = SudokuState()
    target = int(N * N * fill_pct / 100)

    cells = [(r, c) for r in range(N) for c in range(N)]
    random.shuffle(cells)

    filled = 0
    for r, c in cells:
        if filled >= target:
            break
        opts = list(s.get_possible_values(r, c))
        if opts:
            s.grid[r, c] = random.choice(opts)
            filled += 1
    return s


# ============================================================================
# 6.  IMPRESIÓN DE LA RUTA DE SOLUCIÓN
# ============================================================================
def print_path(node, show_first=10, show_last=10):
    """Imprime la ruta: estado_anterior - operador - estado_nuevo + g, h, f."""
    path = node.path()
    n_steps = len(path) - 1
    print(f"\nRUTA DE SOLUCIÓN  ({n_steps} pasos)")
    print(f"  raíz: fill={path[0].state.fill_percentage():.1f}%  "
          f"g={path[0].g} h={path[0].h} f={path[0].f}")

    def fmt(i, n):
        r, c, v = n.operator
        return (f"  paso {i:2d}: ({r},{c}) <- {v}  "
                f"| g={n.g:2d} h={n.h:2d} f={n.f:2d} "
                f"fill={n.state.fill_percentage():5.1f}%")

    if n_steps <= show_first + show_last:
        for i in range(1, n_steps + 1):
            print(fmt(i, path[i]))
    else:
        for i in range(1, show_first + 1):
            print(fmt(i, path[i]))
        print(f"  ... ({n_steps - show_first - show_last} pasos más) ...")
        for i in range(n_steps - show_last + 1, n_steps + 1):
            print(fmt(i, path[i]))


# ============================================================================
# 7.  PROGRAMA PRINCIPAL
# ============================================================================
def main(seed=7, max_nodes=200000, max_time=30):
    print("=" * 60)
    print("SUDOKU 9x9 - BÚSQUEDA A*")
    print("=" * 60)

    # ---- estado inicial aleatorio al 15% -----
    initial = random_initial_state(fill_pct=15, seed=seed)
    print(f"\nEstado inicial aleatorio (seed={seed}):")
    print(f"  Celdas totales: {N*N}  |  "
          f"celdas llenas: {initial.filled_count()} "
          f"({initial.fill_percentage():.1f}%)\n")
    print(initial.display())

    # ---- ejecución de A* -----
    tree = SearchTree(initial,
                      max_nodes=max_nodes,
                      max_time=max_time,
                      verbose=True,
                      log_every=200)
    solution, best_partial, stats = tree.a_star()

    # ---- reporte final (siguiendo el PDF) -----
    print("\n" + "=" * 60)
    print("REPORTE FINAL")
    print("=" * 60)
    print(f"Resuelto                         : {stats['solved']}")
    print(f"Nodos expandidos (cerrados)      : {stats['expanded']}")
    print(f"Nodos generados                  : {stats['generated']}")
    print(f"Frontera restante (abiertos)     : {stats['frontier_remaining']}")
    print(f"Factor de ramificación efectivo  : {stats['branching_eff']:.3f}")
    print(f"Tiempo (s)                       : {stats['time_s']:.2f}")

    if solution is not None:
        print("\n>>> ESTADO META ALCANZADO <<<")
        print_path(solution)
        print("\nGrid completo:")
        print(solution.state.display())
    else:
        print(f"\n>>> MEJOR ESTADO PARCIAL "
              f"({best_partial.state.fill_percentage():.1f}% lleno) <<<")
        print_path(best_partial)
        print("\nGrid del mejor parcial alcanzado:")
        print(best_partial.state.display())

    return solution, best_partial, stats


if __name__ == "__main__":
    main()
