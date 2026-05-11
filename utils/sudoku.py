import copy
import heapq
import random
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


# Tablero central (0) con internos (1,2,3,4)
# e internos con externos (5,6,7,8)
for i in range(3):
    for j in range(3):
        agregar_conexion(0, i,     j,     1, i+6, j+6)   # 0 ↔ 1
        agregar_conexion(0, i,     j+6,   2, i+6, j  )   # 0 ↔ 2
        agregar_conexion(0, i+6,   j,     3, i,   j+6)   # 0 ↔ 3
        agregar_conexion(0, i+6,   j+6,   4, i,   j  )   # 0 ↔ 4
        agregar_conexion(1, i,     j,     5, i+6, j+6)   # 1 ↔ 5
        agregar_conexion(2, i,     j+6,   6, i+6, j  )   # 2 ↔ 6
        agregar_conexion(3, i+6,   j,     7, i,   j+6)   # 3 ↔ 7
        agregar_conexion(4, i+6,   j+6,   8, i,   j  )   # 4 ↔ 8


# =========================================================
# 1. ESTADO
# =========================================================

class Estado:
    """
    Representa la configuración completa de los 9 tableros 9x9.
    grid[z][x][y]: tablero z, fila x, columna y.
    """

    def __init__(self, grid=None):
        if grid:
            self.grid = grid
        else:
            self.grid = [
                [[0]*9 for _ in range(9)]
                for _ in range(9)
            ]

    # --------------------------------------------------
    # APLICAR MOVIMIENTO  (operador)
    # --------------------------------------------------

    def aplicar_movimiento(self, z, x, y, valor):
        """Operador: coloca 'valor' en (z,x,y) y propaga a espejos."""
        self.grid[z][x][y] = valor
        if (z, x, y) in CONEXIONES:
            for (ze, xe, ye) in CONEXIONES[(z, x, y)]:
                self.grid[ze][xe][ye] = valor

    # --------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------

    def es_movimiento_valido(self, z, x, y, valor):
        """Verifica fila, columna, subcuadro y espejos."""
        # fila
        if valor in self.grid[z][x]:
            idx = self.grid[z][x].index(valor)
            if idx != y:
                return False
        # columna
        for i in range(9):
            if i != x and self.grid[z][i][y] == valor:
                return False
        # subcuadro 3x3
        sx, sy = (x//3)*3, (y//3)*3
        for i in range(3):
            for j in range(3):
                xx, yy = sx+i, sy+j
                if (xx != x or yy != y) and self.grid[z][xx][yy] == valor:
                    return False
        # espejos
        if (z, x, y) in CONEXIONES:
            for (ze, xe, ye) in CONEXIONES[(z, x, y)]:
                if not self._es_valido_en_espejo(ze, xe, ye, valor):
                    return False
        return True

    def _es_valido_en_espejo(self, z, x, y, valor):
        if valor in self.grid[z][x]:
            idx = self.grid[z][x].index(valor)
            if idx != y:
                return False
        for i in range(9):
            if i != x and self.grid[z][i][y] == valor:
                return False
        sx, sy = (x//3)*3, (y//3)*3
        for i in range(3):
            for j in range(3):
                xx, yy = sx+i, sy+j
                if (xx != x or yy != y) and self.grid[z][xx][yy] == valor:
                    return False
        return True

    # --------------------------------------------------
    # MRV – celda más restringida
    # --------------------------------------------------

    def obtener_celda_mas_restringida(self):
        min_op = 10
        mejor = None
        mejores_vals = []
        for z in range(9):
            for x in range(9):
                for y in range(9):
                    if self.grid[z][x][y] == 0:
                        posibles = [v for v in range(1, 10)
                                    if self.es_movimiento_valido(z, x, y, v)]
                        if len(posibles) == 0:
                            return (z, x, y), []
                        if len(posibles) < min_op:
                            min_op = len(posibles)
                            mejor = (z, x, y)
                            mejores_vals = posibles
        return mejor, mejores_vals

    # --------------------------------------------------
    # PRUEBA DE META
    # --------------------------------------------------

    def esta_resuelto(self):
        for z in range(9):
            for x in range(9):
                for y in range(9):
                    if self.grid[z][x][y] == 0:
                        return False
        return True

    # --------------------------------------------------
    # HASH para estados visitados
    # --------------------------------------------------

    def hash(self):
        return tuple(
            self.grid[z][x][y]
            for z in range(9)
            for x in range(9)
            for y in range(9)
        )

    # --------------------------------------------------
    # CONSISTENCIA INICIAL
    # --------------------------------------------------

    def es_consistente(self):
        """Verifica que no haya conflictos en los valores ya colocados."""
        for z in range(9):
            for x in range(9):
                for y in range(9):
                    v = self.grid[z][x][y]
                    if v != 0:
                        self.grid[z][x][y] = 0
                        valido = self.es_movimiento_valido(z, x, y, v)
                        self.grid[z][x][y] = v
                        if not valido:
                            return False
        return True


# =========================================================
# 2. GENERADOR DE ESTADO INICIAL ALEATORIO
# =========================================================

def generar_estado_aleatorio(porcentaje_relleno=0.20, semilla=None):
    """
    Genera un estado inicial aleatorio con ~porcentaje_relleno de celdas
    prellenadas de forma válida.
 
    Estrategia:
      1. Construye una lista de todas las celdas candidatas (excluye espejos
         para no contar doble) y la baraja.
      2. Recorre la lista en orden aleatorio e intenta colocar un valor válido
         en cada celda hasta alcanzar el objetivo.
      3. Si una celda ya fue rellenada por propagación de espejo, la salta.
 
    Retorna (Estado, fijo) donde 'fijo' es el conjunto de celdas fijas.
    """
    if semilla is not None:
        random.seed(semilla)
 
    estado = Estado()
    fijo   = set()   # (z, x, y) — incluye espejos
 
    # ── 1. celdas candidatas: excluir las que son espejo de otra ────────────
    # Una celda (z,x,y) es "espejo" si existe otra celda que la apunta.
    # Para evitar contar doble, sólo consideramos la celda de menor índice
    # lexicográfico de cada par espejo.
    celdas_principales = []
    es_espejo_de_otra = set()
 
    for z in range(9):
        for x in range(9):
            for y in range(9):
                if (z, x, y) in CONEXIONES:
                    for vecino in CONEXIONES[(z, x, y)]:
                        # si el vecino tiene índice menor, esta es el espejo
                        if vecino < (z, x, y):
                            es_espejo_de_otra.add((z, x, y))
                            break
 
    for z in range(9):
        for x in range(9):
            for y in range(9):
                if (z, x, y) not in es_espejo_de_otra:
                    celdas_principales.append((z, x, y))
 
    # ── 2. barajar y seleccionar ─────────────────────────────────────────────
    random.shuffle(celdas_principales)
 
    # cuántas celdas principales queremos rellenar
    # (el total real será mayor por los espejos propagados)
    objetivo = max(1, int(len(celdas_principales) * porcentaje_relleno))
    colocadas = 0
 
    for (z, x, y) in celdas_principales:
        if colocadas >= objetivo:
            break
 
        # ya rellenada por propagación de algún espejo anterior
        if estado.grid[z][x][y] != 0:
            fijo.add((z, x, y))
            colocadas += 1
            continue
 
        # intentar un valor aleatorio válido
        vals = list(range(1, 10))
        random.shuffle(vals)
 
        for v in vals:
            if estado.es_movimiento_valido(z, x, y, v):
                estado.aplicar_movimiento(z, x, y, v)   # propaga espejos
                fijo.add((z, x, y))
 
                # registrar también los espejos como fijos
                if (z, x, y) in CONEXIONES:
                    for espejo in CONEXIONES[(z, x, y)]:
                        fijo.add(espejo)
 
                colocadas += 1
                break
        # si ningún valor es válido para esta celda → simplemente la salta
 
    return estado, fijo
# =========================================================
# 3. NODO A*
# =========================================================

class Nodo:
    """
    Contiene un estado + metadatos del árbol de búsqueda.
    g  = costo acumulado (celdas llenadas desde el inicio)
    h  = heurística (estimación al objetivo)
    f  = g + h
    operador = (z, x, y, valor) que generó este nodo
    """

    def __init__(self, estado, padre=None, g=0, operador=None):
        self.estado    = estado
        self.padre     = padre
        self.g         = g
        self.operador  = operador   # (z, x, y, valor)
        self.h         = self.heuristica()
        self.f         = self.g + self.h

    # --------------------------------------------------
    # HEURÍSTICA: suma de opciones válidas por celda vacía
    # (cuantas menos opciones quedan → más cerca de la meta)
    # --------------------------------------------------

    def heuristica(self):
        score = 0
        for z in range(9):
            for x in range(9):
                for y in range(9):
                    if self.estado.grid[z][x][y] == 0:
                        posibles = sum(
                            1 for v in range(1, 10)
                            if self.estado.es_movimiento_valido(z, x, y, v)
                        )
                        score += posibles
        return score

    # --------------------------------------------------

    def __lt__(self, other):
        return self.f < other.f

    # --------------------------------------------------
    # EXPANDIR
    # --------------------------------------------------

    def expandir(self):
        if self.estado.esta_resuelto():
            return "SOLUCION"

        celda, opciones = self.estado.obtener_celda_mas_restringida()

        if celda is None or len(opciones) == 0:
            return []

        z, x, y = celda
        hijos = []

        for valor in opciones:
            nuevo_grid  = copy.deepcopy(self.estado.grid)
            nuevo_estado = Estado(nuevo_grid)
            nuevo_estado.aplicar_movimiento(z, x, y, valor)

            hijo = Nodo(
                nuevo_estado,
                padre=self,
                g=self.g + 1,
                operador=(z, x, y, valor)
            )
            hijos.append(hijo)

        return hijos


# =========================================================
# 4. ÁRBOL A*
# =========================================================

class ArbolBuscadorAStar:
    """
    Implementa A* con:
    - Conjunto de estados visitados (nodos cerrados)
    - Límites: max_nodos, max_profundidad, max_tiempo
    - Registro de ruta de solución
    - Factor de ramificación efectivo
    """

    def __init__(self, estado_inicial,
                 max_nodos=500_000,
                 max_profundidad=730,
                 max_tiempo=300):

        self.raiz           = Nodo(estado_inicial)
        self.nodos_abiertos  = 0
        self.nodos_cerrados  = 0
        self.backtracks      = 0
        self.max_nodos       = max_nodos
        self.max_profundidad = max_profundidad
        self.max_tiempo      = max_tiempo        # segundos
        self.visitados       = set()             # estados cerrados

    # --------------------------------------------------

    def buscar(self):
        frontera = []
        heapq.heappush(frontera, self.raiz)
        self.nodos_abiertos = 1
        t_inicio = time.time()

        while frontera:

            # ── criterios de parada ──────────────────
            elapsed = time.time() - t_inicio

            if elapsed >= self.max_tiempo:
                print(f"\n[LIMITE] Tiempo máximo alcanzado ({self.max_tiempo}s)")
                mejor = min(frontera, key=lambda n: n.h)
                return mejor.estado, self._ruta(mejor), False

            total = self.nodos_abiertos + self.nodos_cerrados
            if total >= self.max_nodos:
                print(f"\n[LIMITE] Nodos máximos alcanzados ({self.max_nodos})")
                mejor = min(frontera, key=lambda n: n.h)
                return mejor.estado, self._ruta(mejor), False
            # ─────────────────────────────────────────

            nodo_actual = heapq.heappop(frontera)
            self.nodos_abiertos -= 1

            # profundidad
            if nodo_actual.g > self.max_profundidad:
                continue

            # ya visitado
            estado_hash = nodo_actual.estado.hash()
            if estado_hash in self.visitados:
                continue
            self.visitados.add(estado_hash)
            self.nodos_cerrados += 1

            resultado = nodo_actual.expandir()

            # ── solución ────────────────────────────
            if resultado == "SOLUCION":
                elapsed = time.time() - t_inicio
                ruta = self._ruta(nodo_actual)
                print("\n" + "="*50)
                print("✓  SOLUCIÓN ENCONTRADA")
                print("="*50)
                print(f"  Nodos abiertos  : {self.nodos_abiertos}")
                print(f"  Nodos cerrados  : {self.nodos_cerrados}")
                print(f"  Backtracks      : {self.backtracks}")
                print(f"  Profundidad     : {nodo_actual.g}")
                print(f"  Tiempo          : {elapsed:.2f}s")
                print(f"  Pasos de ruta   : {len(ruta)}")
                beff = self._factor_ramificacion_efectivo(
                    nodo_actual.g, self.nodos_cerrados)
                print(f"  b* efectivo     : {beff:.4f}")
                return nodo_actual.estado, ruta, True

            # ── callejón sin salida ──────────────────
            if not resultado:
                self.backtracks += 1
                continue

            # ── insertar hijos ───────────────────────
            for hijo in resultado:
                hijo_hash = hijo.estado.hash()
                if hijo_hash not in self.visitados:
                    heapq.heappush(frontera, hijo)
                    self.nodos_abiertos += 1

        print("\nNO EXISTE SOLUCIÓN")
        return None, [], False

    # --------------------------------------------------
    # RUTA DE SOLUCIÓN: lista de (estado_antes, operador, estado_despues)
    # --------------------------------------------------

    def _ruta(self, nodo):
        pasos = []
        actual = nodo
        while actual.padre is not None:
            pasos.append({
                "operador"       : actual.operador,
                "estado_despues" : actual.estado,
                "estado_antes"   : actual.padre.estado,
                "g"              : actual.g,
            })
            actual = actual.padre
        pasos.reverse()
        return pasos

    # --------------------------------------------------
    # FACTOR DE RAMIFICACIÓN EFECTIVO  b*
    # N = (b*)^d  →  b* ≈ N^(1/d)
    # --------------------------------------------------

    @staticmethod
    def _factor_ramificacion_efectivo(profundidad, nodos):
        if profundidad == 0:
            return 0.0
        return nodos ** (1.0 / profundidad)


# =========================================================
# 5. IMPRESIÓN
# =========================================================

def imprimir_tablero(tablero):
    for i, fila in enumerate(tablero):
        if i % 3 == 0 and i != 0:
            print("  ------+-------+------")
        fila_str = ""
        for j, val in enumerate(fila):
            if j % 3 == 0 and j != 0:
                fila_str += "| "
            fila_str += (str(val) if val != 0 else ".") + " "
        print("  " + fila_str)


def imprimir_estado(estado, titulo="ESTADO"):
    print(f"\n{'='*50}")
    print(f"  {titulo}")
    print(f"{'='*50}")
    for z in range(9):
        print(f"\n  [ TABLERO {z} ]")
        imprimir_tablero(estado.grid[z])


def imprimir_ruta(ruta, max_pasos=10):
    """Muestra los primeros 'max_pasos' de la ruta de solución."""
    print(f"\n{'='*50}")
    print(f"  RUTA DE SOLUCIÓN (primeros {min(max_pasos, len(ruta))} pasos)")
    print(f"{'='*50}")
    for i, paso in enumerate(ruta[:max_pasos]):
        z, x, y, v = paso["operador"]
        print(f"  Paso {i+1:3d} | g={paso['g']:3d} | "
              f"Tablero {z}, fila {x}, col {y}  →  valor {v}")
    if len(ruta) > max_pasos:
        print(f"  ... ({len(ruta) - max_pasos} pasos más)")


# =========================================================
# 6. EJECUCIÓN
# =========================================================

if __name__ == "__main__":

    import sys

    # ── Parámetros ────────────────────────────────────
    PORCENTAJE  = 0.15   # fracción de celdas prellenadas (~15 %)
    SEMILLA     = 42     # None = aleatoria pura
    MAX_NODOS   = 200_000
    MAX_TIEMPO  = 120    # segundos
    # ─────────────────────────────────────────────────

    print("\n" + "="*50)
    print("  SUDOKU 9-TABLEROS  –  Búsqueda A*")
    print("="*50)
    print(f"  Porcentaje relleno inicial : {PORCENTAJE*100:.0f}%")
    print(f"  Semilla aleatoria          : {SEMILLA}")
    print(f"  Límite nodos               : {MAX_NODOS:,}")
    print(f"  Límite tiempo              : {MAX_TIEMPO}s")

    # ── Generar estado inicial aleatorio ─────────────
    estado_inicial, celdas_fijas = generar_estado_aleatorio(
        porcentaje_relleno=PORCENTAJE,
        semilla=SEMILLA
    )

    # ── Verificar consistencia inicial ───────────────
    if not estado_inicial.es_consistente():
        print("\n[ERROR] El estado inicial generado es INCONSISTENTE.")
        print("        El problema no tiene solución con esta configuración.")
        sys.exit(1)

    celdas_prellenadas = sum(
        1 for z in range(9) for x in range(9) for y in range(9)
        if estado_inicial.grid[z][x][y] != 0
    )
    print(f"\n  Celdas prellenadas         : {celdas_prellenadas} / 729")
    imprimir_estado(estado_inicial, "ESTADO INICIAL")

    # ── Búsqueda A* ──────────────────────────────────
    print("\n\nINICIANDO A*...\n")
    arbol = ArbolBuscadorAStar(
        estado_inicial,
        max_nodos=MAX_NODOS,
        max_tiempo=MAX_TIEMPO
    )
    solucion, ruta, es_optima = arbol.buscar()

    # ── Resultados ───────────────────────────────────
    if solucion:
        imprimir_estado(solucion, "ESTADO FINAL")
        imprimir_ruta(ruta)
        if not es_optima:
            print("\n[INFO] Solución parcial: se alcanzó un límite de búsqueda.")
    else:
        print("\nNo se encontró solución.")