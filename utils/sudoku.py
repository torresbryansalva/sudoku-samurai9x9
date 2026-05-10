import copy
import heapq

# =========================================================
# 0. MAPA DE SOLAPAMIENTOS
# =========================================================

CONEXIONES = {}

def agregar_conexion(t1, f1, c1, t2, f2, c2):

    if (t1, f1, c1) not in CONEXIONES:
        CONEXIONES[(t1, f1, c1)] = []

    CONEXIONES[(t1, f1, c1)].append((t2, f2, c2))

    if (t2, f2, c2) not in CONEXIONES:
        CONEXIONES[(t2, f2, c2)] = []

    CONEXIONES[(t2, f2, c2)].append((t1, f1, c1))


# ---------------------------------------------------------
# TABLERO CENTRAL CON INTERNOS
# ---------------------------------------------------------

for i in range(3):
    for j in range(3):

        # 0 ↔ 1
        agregar_conexion(0, i, j,
                          1, i + 6, j + 6)

        # 0 ↔ 2
        agregar_conexion(0, i, j + 6,
                          2, i + 6, j)

        # 0 ↔ 3
        agregar_conexion(0, i + 6, j,
                          3, i, j + 6)

        # 0 ↔ 4
        agregar_conexion(0, i + 6, j + 6,
                          4, i, j)

        # 1 ↔ 5
        agregar_conexion(1, i, j,
                          5, i + 6, j + 6)

        # 2 ↔ 6
        agregar_conexion(2, i, j + 6,
                          6, i + 6, j)

        # 3 ↔ 7
        agregar_conexion(3, i + 6, j,
                          7, i, j + 6)

        # 4 ↔ 8
        agregar_conexion(4, i + 6, j + 6,
                          8, i, j)



# =========================================================
# 1. ESTADO
# =========================================================

class Estado:

    def __init__(self, grid=None):

        if grid:
            self.grid = grid
        else:
            self.grid = [
                [[0 for _ in range(9)] for _ in range(9)]
                for _ in range(9)
            ]

    # -----------------------------------------------------
    # APLICAR MOVIMIENTO
    # -----------------------------------------------------

    def aplicar_movimiento(self, z, x, y, valor):

        self.grid[z][x][y] = valor

        # aplicar en espejos
        if (z, x, y) in CONEXIONES:

            for (ze, xe, ye) in CONEXIONES[(z, x, y)]:

                self.grid[ze][xe][ye] = valor

    # -----------------------------------------------------
    # VALIDACIÓN
    # -----------------------------------------------------

    def es_movimiento_valido(self, z, x, y, valor):

        # fila
        for i in range(9):

            if i != y and self.grid[z][x][i] == valor:
                return False

        # columna
        for i in range(9):

            if i != x and self.grid[z][i][y] == valor:
                return False

        # submatriz
        inicio_x = (x // 3) * 3
        inicio_y = (y // 3) * 3

        for i in range(3):
            for j in range(3):

                xx = inicio_x + i
                yy = inicio_y + j

                if (xx != x or yy != y):

                    if self.grid[z][xx][yy] == valor:
                        return False

        # validar espejos
        if (z, x, y) in CONEXIONES:

            for (ze, xe, ye) in CONEXIONES[(z, x, y)]:

                if not self._es_valido_en_espejo(
                        ze, xe, ye, valor):
                    return False

        return True

    # -----------------------------------------------------

    def _es_valido_en_espejo(self, z, x, y, valor):

        for i in range(9):

            if i != y and self.grid[z][x][i] == valor:
                return False

        for i in range(9):

            if i != x and self.grid[z][i][y] == valor:
                return False

        inicio_x = (x // 3) * 3
        inicio_y = (y // 3) * 3

        for i in range(3):
            for j in range(3):

                xx = inicio_x + i
                yy = inicio_y + j

                if (xx != x or yy != y):

                    if self.grid[z][xx][yy] == valor:
                        return False

        return True

    # -----------------------------------------------------
    # CELDA MÁS RESTRINGIDA (MRV)
    # -----------------------------------------------------

    def obtener_celda_mas_restringida(self):

        min_opciones = 10

        mejor_celda = None

        opciones_validas = []

        for z in range(9):

            for x in range(9):

                for y in range(9):

                    if self.grid[z][x][y] == 0:

                        posibles = []

                        for v in range(1, 10):

                            if self.es_movimiento_valido(
                                    z, x, y, v):

                                posibles.append(v)

                        cantidad = len(posibles)

                        # sin solución
                        if cantidad == 0:
                            return (z, x, y), []

                        if cantidad < min_opciones:

                            min_opciones = cantidad

                            mejor_celda = (z, x, y)

                            opciones_validas = posibles

        return mejor_celda, opciones_validas

    # -----------------------------------------------------
    # OBJETIVO
    # -----------------------------------------------------

    def esta_resuelto(self):

        for z in range(9):
            for x in range(9):
                for y in range(9):

                    if self.grid[z][x][y] == 0:
                        return False

        return True
    
# =========================================================
# 2. NODO A*
# =========================================================

class Nodo:

    def __init__(self, estado, padre=None, g=0):

        self.estado = estado

        self.padre = padre

        # costo acumulado
        self.g = g

        # heurística
        self.h = self.heuristica()

        # función A*
        self.f = self.g + self.h

    # -----------------------------------------------------
    # HEURÍSTICA
    # -----------------------------------------------------

    def heuristica(self):

        score = 0

        for z in range(9):

            for x in range(9):

                for y in range(9):

                    if self.estado.grid[z][x][y] == 0:

                        posibles = 0

                        for v in range(1, 10):

                            if self.estado.es_movimiento_valido(
                                    z, x, y, v):

                                posibles += 1

                        score += posibles

        return score

    # -----------------------------------------------------
    # PRIORIDAD EN HEAP
    # -----------------------------------------------------

    def __lt__(self, other):

        return self.f < other.f

    # -----------------------------------------------------
    # EXPANDIR
    # -----------------------------------------------------

    def expandir(self):

        if self.estado.esta_resuelto():
            return "SOLUCION"

        celda, opciones = (
            self.estado.obtener_celda_mas_restringida()
        )

        if celda is None:
            return []

        if len(opciones) == 0:
            return []

        z, x, y = celda

        hijos = []

        for valor in opciones:

            nuevo_grid = copy.deepcopy(
                self.estado.grid
            )

            nuevo_estado = Estado(nuevo_grid)

            nuevo_estado.aplicar_movimiento(
                z, x, y, valor
            )

            hijo = Nodo(
                nuevo_estado,
                padre=self,
                g=self.g + 1
            )

            hijos.append(hijo)

        return hijos
    

# =========================================================
# 3. A*
# =========================================================

class ArbolBuscadorAStar:

    def __init__(self, estado_inicial):

        self.raiz = Nodo(estado_inicial)

        self.nodos_visitados = 0

        self.backtracks = 0

    # -----------------------------------------------------

    def buscar(self):

        frontera = []

        heapq.heappush(frontera, self.raiz)

        while frontera:

            nodo_actual = heapq.heappop(frontera)

            self.nodos_visitados += 1

            resultado = nodo_actual.expandir()

            # solución
            if resultado == "SOLUCION":

                print("\nSOLUCIÓN ENCONTRADA")
                print("Nodos visitados:",
                      self.nodos_visitados)

                print("Backtracks:",
                      self.backtracks)

                return nodo_actual.estado

            # callejón sin salida
            if not resultado:

                self.backtracks += 1

                continue

            # insertar hijos
            for hijo in resultado:

                heapq.heappush(
                    frontera,
                    hijo
                )

        print("\nNO EXISTE SOLUCIÓN")

        return None
    
# =========================================================
# 4. IMPRESIÓN
# =========================================================

def imprimir_tablero(tablero):

    for fila in tablero:

        print(" ".join(str(x) for x in fila))


def imprimir_estado(estado):

    for z in range(9):

        print("\n========================")
        print(f"TABLERO {z}")
        print("========================")

        imprimir_tablero(estado.grid[z])

# =========================================================
# 5. EJECUCIÓN
# =========================================================

if __name__ == "__main__":

    estado_inicial = Estado()

    # =====================================================
    # EJEMPLOS
    # =====================================================

    # CENTRAL
    estado_inicial.aplicar_movimiento(0, 0, 0, 5)
    estado_inicial.aplicar_movimiento(0, 0, 1, 3)
    estado_inicial.aplicar_movimiento(0, 1, 0, 6)

    # TABLERO 1
    estado_inicial.aplicar_movimiento(1, 4, 4, 7)

    # TABLERO 2
    estado_inicial.aplicar_movimiento(2, 3, 3, 2)

    # =====================================================

    print("\nINICIANDO A*...\n")

    arbol = ArbolBuscadorAStar(
        estado_inicial
    )

    solucion = arbol.buscar()

    if solucion:

        imprimir_estado(solucion)