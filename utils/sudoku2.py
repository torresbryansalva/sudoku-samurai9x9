"""
sudoku2.py — Sudoku 9 Tableros resuelto con DFS + backtracking + MRV.

Misma topologia (CONEXIONES, Estado, generador) que sudoku.py, pero el
solver no usa heap ni heuristica con f=g+h: hace busqueda en profundidad
iterativa, muta el estado in-place, deshace al hacer backtrack y elige
la celda mas restringida en cada paso (MRV con forward checking).

Ventajas vs A*:
  - Memoria O(profundidad), no O(nodos_cerrados).
  - Sin copia de estado por hijo: aplicar + deshacer es O(1) amortizado.
  - Mismas guardas de tiempo / nodos / profundidad.
"""

import copy
import random
import sys
import time


# =========================================================
# 0. MAPA DE SOLAPAMIENTOS (CONEXIONES ENTRE TABLEROS)
# =========================================================

CONEXIONES = {}

def agregar_conexion(t1, f1, c1, t2, f2, c2):
    if (t1, f1, c1) not in CONEXIONES:
        CONEXIONES[(t1, f1, c1)] = []
    CONEXIONES[(t1, f1, c1)].append((t2, f2, c2))

    if (t2, f2, c2) not in CONEXIONES:
        CONEXIONES[(t2, f2, c2)] = []
    CONEXIONES[(t2, f2, c2)].append((t1, f1, c1))


for i in range(3):
    for j in range(3):
        agregar_conexion(0, i,     j,     1, i+6, j+6)
        agregar_conexion(0, i,     j+6,   2, i+6, j  )
        agregar_conexion(0, i+6,   j,     3, i,   j+6)
        agregar_conexion(0, i+6,   j+6,   4, i,   j  )
        agregar_conexion(1, i,     j,     5, i+6, j+6)
        agregar_conexion(2, i,     j+6,   6, i+6, j  )
        agregar_conexion(3, i+6,   j,     7, i,   j+6)
        agregar_conexion(4, i+6,   j+6,   8, i,   j  )


# Celdas representantes (la "menor" de cada grupo espejo). DFS no usa
# esto como heuristica, pero se mantiene por compatibilidad con utilidades
# y para que _vacias_principales tenga el mismo significado que en sudoku.py.
ES_PRINCIPAL = set()
for _z in range(9):
    for _x in range(9):
        for _y in range(9):
            _cell = (_z, _x, _y)
            _vecinos = CONEXIONES.get(_cell, ())
            if all(_cell < _v for _v in _vecinos):
                ES_PRINCIPAL.add(_cell)


# Tabla Zobrist. DFS no la usa para cierre (no hay set de visitados:
# el grafo de busqueda es un arbol), pero la dejamos para que Estado
# sea intercambiable con el de sudoku.py.
_zob_rng = random.Random(0xC0FFEE_BEEF)
_ZOBRIST = [
    [
        [
            [_zob_rng.getrandbits(64) for _ in range(10)]
            for _ in range(9)
        ]
        for _ in range(9)
    ]
    for _ in range(9)
]


# =========================================================
# 1. ESTADO  (igual que sudoku.py + deshacer_movimiento)
# =========================================================

class Estado:

    __slots__ = ("grid", "filas", "cols", "cajas",
                 "_vacias", "_vacias_principales", "_hash")

    def __init__(self, grid=None):
        if grid is not None:
            self.grid = grid
        else:
            self.grid = [
                [[0]*9 for _ in range(9)]
                for _ in range(9)
            ]

        self.filas = [[set() for _ in range(9)] for _ in range(9)]
        self.cols  = [[set() for _ in range(9)] for _ in range(9)]
        self.cajas = [
            [[set() for _ in range(3)] for _ in range(3)]
            for _ in range(9)
        ]
        self._vacias = 0
        self._vacias_principales = 0
        self._hash = 0

        for z in range(9):
            grid_z = self.grid[z]
            for x in range(9):
                row = grid_z[x]
                for y in range(9):
                    v = row[y]
                    if v == 0:
                        self._vacias += 1
                        if (z, x, y) in ES_PRINCIPAL:
                            self._vacias_principales += 1
                    else:
                        self.filas[z][x].add(v)
                        self.cols[z][y].add(v)
                        self.cajas[z][x // 3][y // 3].add(v)
                        self._hash ^= _ZOBRIST[z][x][y][v]

    def copia(self):
        nuevo = Estado.__new__(Estado)
        nuevo.grid = [
            [row[:] for row in board]
            for board in self.grid
        ]
        nuevo.filas = [
            [s.copy() for s in self.filas[z]]
            for z in range(9)
        ]
        nuevo.cols = [
            [s.copy() for s in self.cols[z]]
            for z in range(9)
        ]
        nuevo.cajas = [
            [[s.copy() for s in row] for row in self.cajas[z]]
            for z in range(9)
        ]
        nuevo._vacias = self._vacias
        nuevo._vacias_principales = self._vacias_principales
        nuevo._hash = self._hash
        return nuevo

    # --------------------------------------------------
    # APLICAR / DESHACER
    # --------------------------------------------------

    def aplicar_movimiento(self, z, x, y, valor):
        self._poner(z, x, y, valor)
        conex = CONEXIONES.get((z, x, y))
        if conex:
            for (ze, xe, ye) in conex:
                self._poner(ze, xe, ye, valor)

    def deshacer_movimiento(self, z, x, y, valor):
        """Inverso exacto de aplicar_movimiento. Asume que el ultimo
        cambio en (z,x,y) y sus espejos fue precisamente 'valor'."""
        self._quitar(z, x, y, valor)
        conex = CONEXIONES.get((z, x, y))
        if conex:
            for (ze, xe, ye) in conex:
                self._quitar(ze, xe, ye, valor)

    def _poner(self, z, x, y, valor):
        actual = self.grid[z][x][y]
        if actual == valor:
            return
        if actual != 0:
            self.filas[z][x].discard(actual)
            self.cols[z][y].discard(actual)
            self.cajas[z][x // 3][y // 3].discard(actual)
            self._hash ^= _ZOBRIST[z][x][y][actual]
        else:
            self._vacias -= 1
            if (z, x, y) in ES_PRINCIPAL:
                self._vacias_principales -= 1
        self.grid[z][x][y] = valor
        self.filas[z][x].add(valor)
        self.cols[z][y].add(valor)
        self.cajas[z][x // 3][y // 3].add(valor)
        self._hash ^= _ZOBRIST[z][x][y][valor]

    def _quitar(self, z, x, y, valor):
        """Saca 'valor' de (z,x,y) dejando la celda vacia (0)."""
        if self.grid[z][x][y] != valor:
            return
        self.filas[z][x].discard(valor)
        self.cols[z][y].discard(valor)
        self.cajas[z][x // 3][y // 3].discard(valor)
        self._hash ^= _ZOBRIST[z][x][y][valor]
        self.grid[z][x][y] = 0
        self._vacias += 1
        if (z, x, y) in ES_PRINCIPAL:
            self._vacias_principales += 1

    # --------------------------------------------------
    # VALIDACION / META / MRV / CONSISTENCIA  (identico a sudoku.py)
    # --------------------------------------------------

    def es_movimiento_valido(self, z, x, y, valor):
        if valor in self.filas[z][x]:
            return False
        if valor in self.cols[z][y]:
            return False
        if valor in self.cajas[z][x // 3][y // 3]:
            return False
        conex = CONEXIONES.get((z, x, y))
        if conex:
            for (ze, xe, ye) in conex:
                if valor in self.filas[ze][xe]:
                    return False
                if valor in self.cols[ze][ye]:
                    return False
                if valor in self.cajas[ze][xe // 3][ye // 3]:
                    return False
        return True

    def obtener_celda_mas_restringida(self):
        min_op = 10
        mejor = None
        mejores_vals = []
        for z in range(9):
            grid_z = self.grid[z]
            filas_z = self.filas[z]
            cols_z = self.cols[z]
            cajas_z = self.cajas[z]
            for x in range(9):
                row = grid_z[x]
                fila_set = filas_z[x]
                bx = x // 3
                for y in range(9):
                    if row[y] != 0:
                        continue
                    by = y // 3
                    caja_set = cajas_z[bx][by]
                    col_set = cols_z[y]
                    conex = CONEXIONES.get((z, x, y))

                    posibles = []
                    for v in range(1, 10):
                        if v in fila_set or v in col_set or v in caja_set:
                            continue
                        if conex:
                            ok = True
                            for (ze, xe, ye) in conex:
                                if (v in self.filas[ze][xe] or
                                        v in self.cols[ze][ye] or
                                        v in self.cajas[ze][xe // 3][ye // 3]):
                                    ok = False
                                    break
                            if not ok:
                                continue
                        posibles.append(v)
                        if len(posibles) >= min_op:
                            break

                    n = len(posibles)
                    if n == 0:
                        return (z, x, y), []
                    if n < min_op:
                        min_op = n
                        mejor = (z, x, y)
                        mejores_vals = posibles
        return mejor, mejores_vals

    def esta_resuelto(self):
        return self._vacias == 0

    def hash(self):
        return self._hash

    def es_consistente(self):
        for z in range(9):
            grid_z = self.grid[z]
            for x in range(9):
                row_vals = [v for v in grid_z[x] if v != 0]
                if len(row_vals) != len(set(row_vals)):
                    return False
            for y in range(9):
                col_vals = [grid_z[i][y] for i in range(9) if grid_z[i][y] != 0]
                if len(col_vals) != len(set(col_vals)):
                    return False
            for bx in range(3):
                for by in range(3):
                    box_vals = []
                    for i in range(3):
                        for j in range(3):
                            v = grid_z[bx*3 + i][by*3 + j]
                            if v != 0:
                                box_vals.append(v)
                    if len(box_vals) != len(set(box_vals)):
                        return False
        for (z, x, y), espejos in CONEXIONES.items():
            v = self.grid[z][x][y]
            if v == 0:
                continue
            for (ze, xe, ye) in espejos:
                ve = self.grid[ze][xe][ye]
                if ve != 0 and ve != v:
                    return False
        return True


# =========================================================
# 2. GENERADOR DE ESTADO INICIAL ALEATORIO (identico a sudoku.py)
# =========================================================

def generar_estado_aleatorio(porcentaje_relleno=0.15, semilla=None):
    if semilla is not None:
        random.seed(semilla)

    estado = Estado()
    fijo   = set()

    celdas_principales = []
    es_espejo_de_otra = set()

    for z in range(9):
        for x in range(9):
            for y in range(9):
                if (z, x, y) in CONEXIONES:
                    for vecino in CONEXIONES[(z, x, y)]:
                        if vecino < (z, x, y):
                            es_espejo_de_otra.add((z, x, y))
                            break

    for z in range(9):
        for x in range(9):
            for y in range(9):
                if (z, x, y) not in es_espejo_de_otra:
                    celdas_principales.append((z, x, y))

    random.shuffle(celdas_principales)
    objetivo = max(1, int(len(celdas_principales) * porcentaje_relleno))
    colocadas = 0

    for (z, x, y) in celdas_principales:
        if colocadas >= objetivo:
            break

        if estado.grid[z][x][y] != 0:
            fijo.add((z, x, y))
            colocadas += 1
            continue

        vals = list(range(1, 10))
        random.shuffle(vals)

        for v in vals:
            if estado.es_movimiento_valido(z, x, y, v):
                estado.aplicar_movimiento(z, x, y, v)
                fijo.add((z, x, y))
                if (z, x, y) in CONEXIONES:
                    for espejo in CONEXIONES[(z, x, y)]:
                        fijo.add(espejo)
                colocadas += 1
                break

    return estado, fijo


# =========================================================
# 3. BUSCADOR DFS + BACKTRACKING + MRV
# =========================================================

class ArbolBuscadorDFS:
    """
    DFS iterativo con backtracking y MRV + forward checking.

    No usa heap, no usa set de visitados (el espacio de busqueda es un
    arbol: cada movimiento es irreversible mientras no se haga backtrack).
    El estado se muta in-place y se deshace al retroceder.

    La pila guarda, por nivel:  (celda, valor_actual, alternativas_pendientes)
      - Al hacer backtrack: pop, deshacer 'valor_actual', si quedan
        alternativas probar la siguiente; si no, seguir subiendo.

    Stats expuestas para compatibilidad con el visualizador:
      nodos_cerrados, nodos_abiertos (= |pila|), backtracks.
    """

    def __init__(self, estado_inicial,
                 max_nodos=2_000_000,
                 max_profundidad=730,
                 max_tiempo=300):
        self.estado_inicial  = estado_inicial
        self.estado          = estado_inicial.copia()
        self.nodos_cerrados  = 0
        self.nodos_abiertos  = 0
        self.backtracks      = 0
        self.max_nodos       = max_nodos
        self.max_profundidad = max_profundidad
        self.max_tiempo      = max_tiempo
        self.profundidad_max_alcanzada = 0

    # --------------------------------------------------

    def buscar(self):
        pila = []
        # Mejor parcial: lista de (celda, valor) que reproduce el estado
        # mas lleno alcanzado. Se guarda como snapshot al mejorar _vacias.
        mejor_vacias = self.estado._vacias
        mejor_ops    = []

        t_inicio = time.time()
        t_ultimo_log = t_inicio
        LOG_INTERVALO = 2.0

        while True:
            elapsed = time.time() - t_inicio

            if elapsed >= self.max_tiempo:
                print(f"\n[LIMITE] Tiempo maximo alcanzado ({self.max_tiempo}s)",
                      flush=True)
                return self._reconstruir(mejor_ops, False)

            if self.nodos_cerrados >= self.max_nodos:
                print(f"\n[LIMITE] Nodos maximos alcanzados ({self.max_nodos})",
                      flush=True)
                return self._reconstruir(mejor_ops, False)

            ahora = time.time()
            if ahora - t_ultimo_log >= LOG_INTERVALO:
                self._log(elapsed, len(pila))
                t_ultimo_log = ahora

            if self.estado.esta_resuelto():
                elapsed = time.time() - t_inicio
                ops = [(c, v) for (c, v, _) in pila]
                estado_final, ruta, _ = self._reconstruir(ops, True)
                print("\n" + "=" * 50, flush=True)
                print("  SOLUCION ENCONTRADA", flush=True)
                print("=" * 50, flush=True)
                print(f"  Nodos cerrados  : {self.nodos_cerrados:,}", flush=True)
                print(f"  Backtracks      : {self.backtracks:,}", flush=True)
                print(f"  Profundidad     : {len(pila)}", flush=True)
                print(f"  Profundidad max : {self.profundidad_max_alcanzada}",
                      flush=True)
                print(f"  Tiempo          : {elapsed:.2f}s", flush=True)
                print(f"  Pasos de ruta   : {len(ruta)}", flush=True)
                return estado_final, ruta, True

            celda, opciones = self.estado.obtener_celda_mas_restringida()

            if celda is None:
                # No hay celdas vacias pero _vacias != 0: imposible si los
                # indices estan bien. Defensa por si acaso.
                return self._reconstruir(mejor_ops, False)

            if not opciones:
                # Dead-end por forward checking: backtrack
                if not self._backtrack(pila):
                    print("\nNO EXISTE SOLUCION", flush=True)
                    return None, [], False
                self.backtracks += 1
                continue

            if len(pila) >= self.max_profundidad:
                if not self._backtrack(pila):
                    return self._reconstruir(mejor_ops, False)
                self.backtracks += 1
                continue

            v = opciones[0]
            self.estado.aplicar_movimiento(celda[0], celda[1], celda[2], v)
            pila.append((celda, v, opciones[1:]))
            self.nodos_cerrados += 1
            self.nodos_abiertos = len(pila)

            if len(pila) > self.profundidad_max_alcanzada:
                self.profundidad_max_alcanzada = len(pila)

            if self.estado._vacias < mejor_vacias:
                mejor_vacias = self.estado._vacias
                mejor_ops = [(c, vv) for (c, vv, _) in pila]

    # --------------------------------------------------

    def _backtrack(self, pila):
        """Pop hasta encontrar un nivel con alternativas. Devuelve False
        si la pila se vacia (espacio de busqueda agotado)."""
        while pila:
            celda, v, alternativas = pila.pop()
            self.estado.deshacer_movimiento(celda[0], celda[1], celda[2], v)
            if alternativas:
                v2 = alternativas[0]
                self.estado.aplicar_movimiento(celda[0], celda[1], celda[2], v2)
                pila.append((celda, v2, alternativas[1:]))
                self.nodos_cerrados += 1
                self.nodos_abiertos = len(pila)
                return True
        self.nodos_abiertos = 0
        return False

    # --------------------------------------------------

    def _reconstruir(self, ops, es_completa):
        """Aplica ops sobre una copia del estado inicial para devolver
        (estado, ruta) coherentes con el formato del visualizador."""
        estado = self.estado_inicial.copia()
        ruta = []
        for i, (celda, v) in enumerate(ops):
            estado.aplicar_movimiento(celda[0], celda[1], celda[2], v)
            ruta.append({
                "operador"       : (celda[0], celda[1], celda[2], v),
                "estado_despues" : None,
                "estado_antes"   : None,
                "g"              : i + 1,
            })
        return estado, ruta, es_completa

    # --------------------------------------------------

    def _log(self, elapsed, profundidad):
        vacias = self.estado._vacias
        llenadas = 729 - vacias
        pct = llenadas / 729 * 100
        beff = self._factor_ramificacion_efectivo(
            profundidad, self.nodos_cerrados)
        print(
            f"  [{elapsed:6.1f}s]"
            f"  nodos={self.nodos_cerrados:>7,}"
            f"  pila={profundidad:>4}"
            f"  prof_max={self.profundidad_max_alcanzada:>4}"
            f"  llenas={llenadas:>3}/729 ({pct:4.1f}%)"
            f"  backt={self.backtracks:>5,}"
            f"  b*={beff:.4f}",
            flush=True,
        )

    @staticmethod
    def _factor_ramificacion_efectivo(profundidad, nodos):
        if profundidad == 0:
            return 0.0
        return nodos ** (1.0 / profundidad)


# =========================================================
# 4. IMPRESION
# =========================================================

def imprimir_tablero(tablero):
    for i, fila in enumerate(tablero):
        if i % 3 == 0 and i != 0:
            print("  ------+-------+------", flush=True)
        fila_str = ""
        for j, val in enumerate(fila):
            if j % 3 == 0 and j != 0:
                fila_str += "| "
            fila_str += (str(val) if val != 0 else ".") + " "
        print("  " + fila_str, flush=True)


def imprimir_estado(estado, titulo="ESTADO"):
    print(f"\n{'='*50}", flush=True)
    print(f"  {titulo}", flush=True)
    print(f"{'='*50}", flush=True)
    for z in range(9):
        print(f"\n  [ TABLERO {z} ]", flush=True)
        imprimir_tablero(estado.grid[z])


def imprimir_ruta(ruta, max_pasos=10):
    print(f"\n{'='*50}", flush=True)
    print(f"  RUTA DE SOLUCION (primeros {min(max_pasos, len(ruta))} pasos)",
          flush=True)
    print(f"{'='*50}", flush=True)
    for i, paso in enumerate(ruta[:max_pasos]):
        z, x, y, v = paso["operador"]
        print(f"  Paso {i+1:3d} | g={paso['g']:3d} | "
              f"Tablero {z}, fila {x}, col {y}  ->  valor {v}", flush=True)
    if len(ruta) > max_pasos:
        print(f"  ... ({len(ruta) - max_pasos} pasos mas)", flush=True)


# =========================================================
# 5. EJECUCION DIRECTA
# =========================================================

if __name__ == "__main__":

    PORCENTAJE  = 0.15
    SEMILLA     = 42
    MAX_NODOS   = 2_000_000
    MAX_TIEMPO  = 180

    print("\n" + "="*50, flush=True)
    print("  SUDOKU 9-TABLEROS  -  Busqueda DFS + Backtracking + MRV",
          flush=True)
    print("="*50, flush=True)
    print(f"  Porcentaje relleno inicial : {PORCENTAJE*100:.0f}%", flush=True)
    print(f"  Semilla aleatoria          : {SEMILLA}", flush=True)
    print(f"  Limite nodos               : {MAX_NODOS:,}", flush=True)
    print(f"  Limite tiempo              : {MAX_TIEMPO}s", flush=True)

    estado_inicial, celdas_fijas = generar_estado_aleatorio(
        porcentaje_relleno=PORCENTAJE,
        semilla=SEMILLA
    )

    if not estado_inicial.es_consistente():
        print("\n[ERROR] El estado inicial generado es INCONSISTENTE.",
              flush=True)
        sys.exit(1)

    celdas_prellenadas = sum(
        1 for z in range(9) for x in range(9) for y in range(9)
        if estado_inicial.grid[z][x][y] != 0
    )
    print(f"\n  Celdas prellenadas         : {celdas_prellenadas} / 729",
          flush=True)
    imprimir_estado(estado_inicial, "ESTADO INICIAL")

    print("\n\nINICIANDO DFS...\n", flush=True)
    arbol = ArbolBuscadorDFS(
        estado_inicial,
        max_nodos=MAX_NODOS,
        max_tiempo=MAX_TIEMPO
    )
    solucion, ruta, es_completa = arbol.buscar()

    if solucion:
        imprimir_estado(solucion, "ESTADO FINAL")
        imprimir_ruta(ruta)
        if not es_completa:
            print("\n[INFO] Solucion parcial: se alcanzo un limite.",
                  flush=True)
    else:
        print("\nNo se encontro solucion.", flush=True)
