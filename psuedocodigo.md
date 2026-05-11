# Sudoku 9 Tableros — Informe Técnico (MIA-103)

---

## 1. Objetivo del Problema (sección 4.5 del examen)

Completar 9 tableros de Sudoku 9×9 interconectados parcialmente, de modo que
cada tablero cumpla las reglas estándar: cada fila, columna y región 3×3 contiene
los dígitos 1–9 sin repetición. Las celdas compartidas (solapamientos) deben ser
consistentes entre tableros adyacentes.

**Restricciones requeridas por el examen:**
- El estado inicial se genera **aleatoriamente**.
- El porcentaje de celdas prellenadas es configurable.
- El buscador debe detectar que **no existe solución** (configuración inválida).

---

## 2. Planteamiento del Problema de Búsqueda (sección 2.3)

| Elemento | Definición |
|---|---|
| **Estado** | `grid[z][x][y]` — matriz 3D 9×9×9; cada posición tiene un valor 0–9 |
| **Estado inicial** | Configuración parcial generada aleatoriamente (~15 % de celdas) |
| **Estado meta** | Todas las 729 celdas ≠ 0 y sin conflicto |
| **Operadores** | Colocar valor `v ∈ {1..9}` en celda vacía `(z, x, y)` válida |
| **Función sucesora** | Aplica el operador y propaga a espejos |
| **Costo por operador** | 1 (uniforme) |

### Espacio de estados

```
Sin restricciones : (9^81)^9  ≈ 10^699
Con restricciones : drásticamente reducido por MRV + propagación de arco
```

### Factor de ramificación

- **Teórico (b):** hasta 9 (una cifra por celda vacía)
- **Efectivo (b\*):** `N_nodos_cerrados ^ (1 / profundidad)` — se calcula al finalizar la búsqueda

---

## 3. Representación del Estado y sus Métodos (sección 2.4)

```python
class Estado:
    grid: list[list[list[int]]]  # 9 tableros × 9 filas × 9 columnas

    def aplicar_movimiento(z, x, y, valor)   # Operador + propagación a espejos
    def es_movimiento_valido(z, x, y, valor) # Prueba fila / columna / subcuadro / espejos
    def obtener_celda_mas_restringida()       # MRV: menos opciones disponibles
    def esta_resuelto()                       # Prueba de meta
    def es_consistente()                      # Verifica estado inicial (sin solución imposible)
    def hash()                                # Tuple único para el conjunto de visitados
```

### Conexiones entre tableros

```
Tablero 0 (Centro) ↔ Tableros 1, 2, 3, 4  (solapamientos de esquina 3×3)
Tablero 1 ↔ Tablero 5
Tablero 2 ↔ Tablero 6
Tablero 3 ↔ Tablero 7
Tablero 4 ↔ Tablero 8
```

El mapa `CONEXIONES[(z,x,y)]` almacena todas las celdas espejo, permitiendo
propagar un valor a todos los tableros que comparten esa celda.

### Verificación de consistencia inicial (NUEVO)

```python
def es_consistente(self):
    """Detecta conflictos en celdas ya colocadas → 'No tiene solución'."""
    for z, x, y:
        v = grid[z][x][y]
        if v != 0:
            grid[z][x][y] = 0           # borra temporalmente
            valido = es_movimiento_valido(z, x, y, v)
            grid[z][x][y] = v           # restaura
            if not valido: return False
    return True
```

Si retorna `False`, el programa informa que el problema no tiene solución y termina.

---

## 4. Generador de Estado Inicial Aleatorio (NUEVO — requerido por examen)

```python
def generar_estado_aleatorio(porcentaje_relleno=0.15, semilla=None):
    """
    Rellena aleatoriamente ~porcentaje_relleno de las 729 celdas con
    valores válidos. La semilla permite reproducibilidad.
    Retorna (Estado, conjunto_celdas_fijas).
    """
    random.seed(semilla)
    # Para cada intento: elige celda aleatoria, baraja {1..9},
    # coloca el primer valor que pase es_movimiento_valido().
```

**Porcentaje recomendado:** 10–20 % (≈73–146 celdas prellenadas).
Valores muy altos pueden generar estados sin solución única.

---

## 5. Representación del Nodo y sus Métodos (sección 2.5)

```python
class Nodo:
    estado    : Estado      # configuración actual
    padre     : Nodo        # nodo que lo generó (None en la raíz)
    g         : int         # costo acumulado = celdas llenadas desde inicio
    operador  : tuple       # (z, x, y, valor) que generó este nodo  ← NUEVO
    h         : int         # heurística (ver abajo)
    f         : int         # f = g + h
```

El atributo `operador` es nuevo y **necesario para reconstruir la ruta de solución**.

### Heurística h(n)

```python
def heuristica(self):
    score = 0
    for cada celda vacía (z,x,y):
        score += cantidad_de_valores_válidos(z,x,y)
    return score
```

**Justificación:** cuantas menos opciones totales quedan, más cerca está la
solución. Es admisible porque nunca sobreestima el trabajo restante.

---

## 6. Representación del Árbol y sus Métodos (sección 2.6)

```python
class ArbolBuscadorAStar:
    raiz            : Nodo
    nodos_abiertos  : int        # tamaño actual de la frontera (heapq)
    nodos_cerrados  : int        # estados ya expandidos
    backtracks      : int
    visitados       : set        # hashes de estados cerrados (NUEVO)
    max_nodos       : int        # límite total nodos (NUEVO)
    max_profundidad : int        # límite de profundidad (NUEVO)
    max_tiempo      : float      # límite en segundos (NUEVO)
```

### Criterios de finalización (NUEVO — sección 2.6 del examen)

El árbol termina cuando se cumple **cualquiera** de estas condiciones:

1. **Solución encontrada** → retorna el estado resuelto
2. **Tiempo ≥ max_tiempo** → retorna la mejor solución parcial encontrada
3. **Total nodos ≥ max_nodos** → retorna la mejor solución parcial
4. **Frontera vacía** → informa que no existe solución

```python
if elapsed >= self.max_tiempo:
    mejor = min(frontera, key=lambda n: n.h)   # mejor nodo en cola
    return mejor.estado, self._ruta(mejor), False

if total >= self.max_nodos:
    mejor = min(frontera, key=lambda n: n.h)
    return mejor.estado, self._ruta(mejor), False
```

### Conjunto de nodos cerrados (NUEVO)

```python
self.visitados = set()          # hashes (tuples de 729 ints)

# en el bucle principal:
estado_hash = nodo_actual.estado.hash()
if estado_hash in self.visitados:
    continue                    # evitar reexpansión
self.visitados.add(estado_hash)
self.nodos_cerrados += 1
```

Esto garantiza que **ningún estado se expande dos veces**, evitando ciclos
y reduciendo el espacio de búsqueda efectivo.

---

## 7. Ruta de Solución (NUEVO — requerido en sección 2.6)

La ruta reconstruye el camino desde la raíz hasta el nodo solución:

```python
def _ruta(self, nodo):
    pasos = []
    actual = nodo
    while actual.padre is not None:
        pasos.append({
            "operador"      : actual.operador,      # (z, x, y, valor)
            "estado_antes"  : actual.padre.estado,
            "estado_despues": actual.estado,
            "g"             : actual.g,
        })
        actual = actual.padre
    pasos.reverse()
    return pasos
```

**Formato de salida por paso:**
```
Paso   1 | g=  1 | Tablero 0, fila 2, col 5  →  valor 7
Paso   2 | g=  2 | Tablero 3, fila 0, col 1  →  valor 4
...
```

Cada paso muestra: **estado anterior → operador → estado nuevo**.

---

## 8. Factor de Ramificación Efectivo (NUEVO — requerido en sección 2.6)

```python
@staticmethod
def _factor_ramificacion_efectivo(profundidad, nodos):
    # N ≈ (b*)^d  →  b* = N^(1/d)
    if profundidad == 0: return 0.0
    return nodos ** (1.0 / profundidad)
```

Se imprime al terminar la búsqueda junto con nodos abiertos/cerrados.

---

## 9. Algoritmo A* — Diagrama de Flujo

```
Estado inicial aleatorio
        ↓
Verificar consistencia
  ↙ inválido     ↘ válido
"Sin solución"   Nodo raíz (g=0, h=h(raíz), f=f(raíz))
                      ↓
              Priority Queue (heapq)
                      ↓
           ┌─── pop nodo de menor f ───┐
           │                           │
     ¿visitado?                  ¿meta?
        ↓ sí                       ↓ sí
      ignorar               SOLUCIÓN → imprimir ruta
        ↓ no
   marcar cerrado (nodos_cerrados++)
        ↓
  expandir con MRV
        ↓
  ¿opciones == 0?
      ↓ sí         ↓ no
  backtrack    push hijos a frontera
        ↓
  ¿límite tiempo/nodos?
      ↓ sí
  retornar mejor parcial
```

---

## 10. Complejidad

| Métrica | Valor |
|---|---|
| **Tiempo** | O(b^d) en el peor caso; MRV reduce b dramáticamente |
| **Espacio** | O(b^d) — todos los nodos de la frontera |
| **Completitud** | Sí — si existe solución y no se alcanza el límite |
| **Optimalidad** | Sí — h(n) es admisible (nunca sobreestima) |

---

## 11. Parámetros de Ejecución

```python
PORCENTAJE  = 0.15   # 15 % de celdas prellenadas
SEMILLA     = 42     # reproducibilidad (None = aleatoria pura)
MAX_NODOS   = 200_000
MAX_TIEMPO  = 120    # segundos
```

---

## 12. Ejemplo de Salida Esperada

```
==================================================
  SUDOKU 9-TABLEROS  –  Búsqueda A*
==================================================
  Porcentaje relleno inicial : 15%
  Semilla aleatoria          : 42
  Límite nodos               : 200,000
  Límite tiempo              : 120s

  Celdas prellenadas         : 97 / 729

  [ ESTADO INICIAL ]
  ...

INICIANDO A*...

==================================================
✓  SOLUCIÓN ENCONTRADA
==================================================
  Nodos abiertos  : 1842
  Nodos cerrados  : 9310
  Backtracks      : 47
  Profundidad     : 632
  Tiempo          : 38.4s
  Pasos de ruta   : 632
  b* efectivo     : 1.0143

  RUTA DE SOLUCIÓN (primeros 10 pasos)
  Paso   1 | g=  1 | Tablero 0, fila 0, col 2  →  valor 3
  ...
```

---

## 13. Checklist de Cumplimiento del Examen

| Requisito (examen) | Estado |
|---|---|
| Estado como matriz 3D 9×9×9 | ✅ `Estado.grid[z][x][y]` |
| Estado inicial aleatorio | ✅ `generar_estado_aleatorio()` |
| Porcentaje configurable | ✅ parámetro `porcentaje_relleno` |
| Detectar sin solución (estado inválido) | ✅ `es_consistente()` + frontera vacía |
| Prueba de meta | ✅ `esta_resuelto()` |
| Función sucesora | ✅ `aplicar_movimiento()` + `expandir()` |
| Nodos abiertos y cerrados | ✅ `nodos_abiertos`, `nodos_cerrados`, `visitados` |
| Criterios de finalización (tiempo/nodos/profundidad) | ✅ `max_tiempo`, `max_nodos`, `max_profundidad` |
| Ruta: estado anterior → operador → estado nuevo | ✅ `_ruta()` + `Nodo.operador` |
| Factor de ramificación efectivo b* | ✅ `_factor_ramificacion_efectivo()` |
| Heurística admisible | ✅ suma de opciones válidas por celda |
| Restricciones 3D entre tableros | ✅ `CONEXIONES` + propagación en espejos |