# Workflow – Sudoku 9×9 con A\*

**Curso:** MIA-103 Fundamentos de Inteligencia Artificial
**Problema:** 4.5 del Anexo 1 (tablero individual 9×9 como el mostrado en el PDF)
**Algoritmo:** A\*
**Estado inicial:** generado aleatoriamente con ~15 % de las casillas llenas.

---

## 1. Planteamiento del problema (PDF §2.2)

Un tablero de Sudoku 9×9 con 81 celdas. Reglas:
- Cada **fila** contiene los dígitos 1–9 sin repetir.
- Cada **columna** contiene los dígitos 1–9 sin repetir.
- Cada **bloque 3×3** contiene los dígitos 1–9 sin repetir.

El estado inicial llena ~15 % de las casillas (≈ 12 celdas con valores aleatorios consistentes). Con 12 pistas se está por debajo del umbral teórico de 17 que garantiza unicidad de solución, por lo que es esperable que el tablero admita **múltiples soluciones**; A\* encontrará una de ellas.

---

## 2. Definición del problema de búsqueda (PDF §2.3)

| Elemento | Definición |
|---|---|
| **Estado** | Matriz 9×9 con valores en {0, 1…9}. `0` = vacía, `1-9` = asignada. |
| **Estado inicial** | Matriz con ~15 % (≈12) de las 81 celdas llenas con valores aleatorios consistentes. |
| **Prueba de meta** | No queda ninguna celda con valor 0. |
| **Operadores** | "Asignar el dígito `v` a la celda vacía `(r,c)`" siempre que `v` sea legal en `(r,c)`. |
| **Función sucesora** | Implementada con heurística **MRV** (Minimum Remaining Values): elige la celda con menor número de valores legales y genera un sucesor por cada valor. |
| **Costo por operador** | 1 (uniforme). |

### Métricas derivadas

| Métrica | Valor / discusión |
|---|---|
| **Factor de ramificación b** | Hasta 9 por celda → b ≤ 9 en el peor caso. |
| **Factor de ramificación efectivo b\*** | Con MRV: ≈ 1.61 en la corrida real (ver §7). |
| **Completez** | A\* es completo en espacios finitos con costos > 0. El Sudoku 9×9 es finito → A\* es completo. |
| **Complejidad** | Tiempo y memoria O(b^d), con d ≤ 81. |
| **Optimalidad** | Garantizada porque `h` es admisible. |
| **Eficiencia / eficacia** | Medibles por `generados/expandidos` y por `% llenado` alcanzado. |

---

## 3. Algoritmo A\* — definición formal de g() y h()

### `g(n)` – costo desde la raíz

```
g(n) = profundidad de n
     = número de operadores aplicados desde el estado inicial
     = número de celdas llenadas desde s0
```

Cada operador tiene costo 1, por lo que `g(n)` coincide con la profundidad.

### `h(n)` – heurística

```
h(n) = número de celdas vacías que aún quedan
       (∞ si alguna celda vacía no tiene ningún valor legal)
```

**Admisibilidad:** cada operador llena exactamente UNA celda, por lo que se necesitan **al menos** `|vacías|` pasos para alcanzar la meta. De hecho `h(n)` es **exacta** cuando el estado `n` es soluble.

**Detección de estados muertos:** si alguna celda vacía tiene 0 valores legales, no hay forma de llegar a la meta desde `n`, por lo que `h(n) = +∞` y A\* nunca lo expande. Poda dura que evita explorar ramas inviables.

### `f(n) = g(n) + h(n)`

Observación importante: cada paso suma 1 a `g` y resta 1 a `h`, por lo que **`f` es constante a lo largo de cualquier camino válido**, igual a `h(s0)`. En la corrida real `f = 69` desde la raíz hasta la meta. Con esta heurística, A\* se comporta efectivamente como un **DFS guiado por MRV**: el desempate por profundidad descendente (preferir el nodo más profundo) lo empuja a llegar rápido a la meta. Esta degeneración es esperada para problemas tipo CSP y se justifica en la literatura (Russell & Norvig, cap. 6).

### Pseudocódigo

```
A*(s0):
    abierta  ← cola de prioridad ordenada por (f, -profundidad, id)
    cerrada  ← {}
    insertar Nodo(s0, g=0, h=h(s0)) en abierta
    mejor_parcial ← nodo_raíz

    mientras abierta no vacía:
        si tiempo > max_time o expandidos > max_nodes: detener
        n ← extraer mínimo de abierta
        si n.estado en cerrada: continuar
        agregar n.estado a cerrada
        si n.estado.fill_% > mejor_parcial.fill_%: mejor_parcial ← n
        si n.estado es meta: retornar (n, n, stats)
        para cada (estado', op, costo) en n.estado.sucesores():
            si estado' en cerrada: continuar
            crear hijo con g'=n.g+costo, h'=h(estado')
            insertar hijo en abierta
    retornar (None, mejor_parcial, stats)   # no se halló solución completa
```

---

## 4. Estructura del programa (PDF §2.4 – §2.6)

| Componente del PDF | Clase / función |
|---|---|
| §2.4 Estados, propiedades y métodos | `SudokuState` |
| §2.5 Nodos, propiedades y métodos | `Node` |
| §2.6 Árbol y métodos | `SearchTree` |
| §2.7 Pruebas | `main()` y `random_initial_state()` |
| §2.8 Análisis | bloque "REPORTE FINAL" al final de `main()` |

### Métodos de cada clase

**`SudokuState`** (estado):
- `get_possible_values(r,c)` → conjunto de dígitos legales para `(r,c)` mirando fila, columna y bloque 3×3
- `successors()` → genera hijos usando MRV
- `is_goal()` → prueba de meta (sin celdas vacías)
- `fill_percentage()`, `filled_count()`, `empty_cells()` → métricas
- `__hash__`, `__eq__` → para usar el estado como clave en el conjunto cerrado
- `display()` → impresión legible con separadores 3×3

**`Node`** (nodo, **no contiene los métodos del estado**):
- `parent`, `operator`, `g`, `h`, `f`, `depth`, `id` → atributos propios
- `path()` → reconstruye la ruta raíz → este nodo

**`SearchTree`** (árbol):
- `open_heap` → cola de prioridad (frontera = nodos abiertos)
- `closed` → conjunto de estados expandidos (nodos cerrados)
- Criterios de paro: `max_nodes`, `max_depth`, `max_time` (PDF §2.6)
- `a_star()` → ejecuta la búsqueda y retorna `(solucion, mejor_parcial, stats)`
- `_stats()` → consolida nodos expandidos, generados, b\*, tiempo

### Criterios de terminación (PDF §2.6)

Si se cumple cualquiera, el algoritmo **entrega el mejor resultado hasta el momento** (definido como el nodo con mayor `fill_percentage()`):

1. `nodes_expanded ≥ max_nodes`
2. `node.depth > max_depth`
3. `elapsed > max_time`

---

## 5. Generación del estado inicial aleatorio

```python
random_initial_state(fill_pct=15, seed=…)
```

1. Crea un grid vacío.
2. Baraja aleatoriamente las 81 celdas.
3. Recorre la lista barajada y, mientras no se llegue al 15 % objetivo, asigna un valor aleatorio entre los **legales en ese momento** (consistencia local). Esto NO garantiza solubilidad global; alineado con el PDF: el agente debe ser capaz de identificar problemas sin solución.

---

## 6. Reporte exigido por el PDF (§2.6)

Al terminar la ejecución se imprime:
- **Ruta de solución**: estado anterior – operador – estado nuevo, con `g`, `h`, `f` por paso
- **Número de nodos abiertos y cerrados**
- **Factor de ramificación efectivo**
- **Grid final** (sea la solución completa o el mejor parcial)

---

## 7. Resultados de la corrida (seed = 7)

### Estado inicial (14.8 % lleno – 12 de 81 celdas)

```
9 . . | . . 3 | . . .
. . . | . . . | . 7 .
. . 5 | . . . | 3 . .
-------------------------
. . 9 | . . 2 | . . .
. . . | 5 . . | 2 . 7
. . . | . 7 . | . . .
-------------------------
. . . | . . . | . . .
. . . | . . . | 1 . .
. . . | . . . | . . .
```

### Reporte final

| Métrica | Valor |
|---|---|
| Resuelto | **True** ✓ |
| Nodos expandidos (cerrados) | 75 |
| Nodos generados | 121 |
| Frontera restante (abiertos) | 46 |
| Factor de ramificación efectivo b\* | **1.613** |
| Tiempo (s) | 0.10 |
| % de llenado del estado meta | **100 %** |
| Profundidad de la solución | 69 |

### Ruta de solución (primeros 10 y últimos 10 pasos)

```
g(s0)=0  h(s0)=69  f(s0)=69

paso  1: (0,6) <- 4  | g= 1 h=68 f=69 fill= 16.0%
paso  2: (3,6) <- 5  | g= 2 h=67 f=69 fill= 17.3%
paso  3: (1,6) <- 6  | g= 3 h=66 f=69 fill= 18.5%
paso  4: (5,6) <- 8  | g= 4 h=65 f=69 fill= 19.8%
paso  5: (6,6) <- 7  | g= 5 h=64 f=69 fill= 21.0%
paso  6: (8,6) <- 9  | g= 6 h=63 f=69 fill= 22.2%
paso  7: (0,7) <- 1  | g= 7 h=62 f=69 fill= 23.5%
paso  8: (0,8) <- 2  | g= 8 h=61 f=69 fill= 24.7%
paso  9: (2,7) <- 8  | g= 9 h=60 f=69 fill= 25.9%
paso 10: (2,8) <- 9  | g=10 h=59 f=69 fill= 27.2%
   ... (49 pasos más) ...
paso 60: (7,4) <- 6  | g=60 h= 9 f=69 fill= 88.9%
paso 61: (7,0) <- 4  | g=61 h= 8 f=69 fill= 90.1%
paso 62: (7,8) <- 8  | g=62 h= 7 f=69 fill= 91.4%
paso 63: (7,5) <- 5  | g=63 h= 6 f=69 fill= 92.6%
paso 64: (7,7) <- 2  | g=64 h= 5 f=69 fill= 93.8%
paso 65: (8,0) <- 6  | g=65 h= 4 f=69 fill= 95.1%
paso 66: (8,4) <- 1  | g=66 h= 3 f=69 fill= 96.3%
paso 67: (8,5) <- 8  | g=67 h= 2 f=69 fill= 97.5%
paso 68: (8,7) <- 5  | g=68 h= 1 f=69 fill= 98.8%
paso 69: (8,8) <- 4  | g=69 h= 0 f=69 fill=100.0%
```

Confirmación experimental: `f = 69` en todo momento, exactamente como predijo el análisis (cada paso baja `h` en 1 y sube `g` en 1).

### Solución encontrada (100 % de llenado)

```
9 6 7 | 8 5 3 | 4 1 2
3 4 8 | 2 9 1 | 6 7 5
1 2 5 | 6 4 7 | 3 8 9
-------------------------
7 3 9 | 1 8 2 | 5 4 6
8 1 4 | 5 3 6 | 2 9 7
2 5 6 | 4 7 9 | 8 3 1
-------------------------
5 8 1 | 9 2 4 | 7 6 3
4 9 3 | 7 6 5 | 1 2 8
6 7 2 | 3 1 8 | 9 5 4
```

---

## 8. Conclusiones cuantitativas (PDF §9)

| Métrica | Valor | Comentario |
|---|---|---|
| Admisibilidad de `h` | Sí (exacta) | Optimalidad garantizada |
| Completez del procedimiento | Sí (en teoría); en la práctica acotada por `max_time/max_nodes` | El espacio finito justifica completez |
| b\* alcanzado | 1.613 | MRV reduce drásticamente la ramificación bruta (≤9 → ≈1.6) |
| Profundidad de la solución | d = 69 | = h(s0) (era de esperar) |
| Tasa de podas | (gen − exp) / gen = 38.0 % | El conjunto cerrado y los estados muertos cortan ≈38% de los hijos |
| Nodos/segundo | ≈ 750 | Cuello de botella: `get_possible_values` |
| Optimalidad efectiva | Trivial | Todas las soluciones tienen la misma profundidad = h(s0) |

---

## 9. Recomendaciones (PDF §10) e implementación

1. **Forward-checking + AC-3 antes de la búsqueda.** Propagar arcos hasta consistencia local reduciría el estado inicial (singles "obligados") sin expandir ningún nodo. *Viable* — basta con iterar `get_possible_values` y aplicar valores únicos hasta punto fijo. Es la técnica estándar para resolver Sudokus humanos.
2. **Heurística no admisible para tie-breaking** (e.g., `h' = h + 0.01·Σ(opciones−1)`). Sacrificaría optimalidad estricta pero podría acelerar el avance. *Viable* en este problema, porque todas las soluciones completas tienen `d = |vacías inicial|`: la "optimalidad" en pasos es trivial.
3. **Cambiar a DFS con backtracking puro + MRV.** Como `f` es constante, A\* no aprovecha su ordenamiento; un DFS clásico usaría O(d) memoria en lugar de O(b^d). *Viable* — y empíricamente más rápido en Sudoku porque evita la sobrecarga del heap.

---

## 10. Cómo correr el código

```bash
python sudoku_9x9_astar.py
```

Para cambiar parámetros desde código:

```python
from sudoku_9x9_astar import main
main(seed=42, max_nodes=50000, max_time=60)
```

---

## 11. Referencias mínimas (PDF §11)

- Russell, S. & Norvig, P. (2021). *Artificial Intelligence: A Modern Approach* (4ª ed.). Pearson. **ISBN 978-0134610993**. Caps. 3–4 (A\*, heurísticas, búsqueda informada) y cap. 6 (CSPs y MRV).
- Hart, P., Nilsson, N., Raphael, B. (1968). "A Formal Basis for the Heuristic Determination of Minimum Cost Paths". *IEEE Trans. Syst. Sci. Cybern.* 4(2):100-107. **DOI 10.1109/TSSC.1968.300136**.
- Knuth, D. (2000). "Dancing Links". arXiv:cs/0011047. **DOI 10.48550/arXiv.cs/0011047** (técnica complementaria para Sudoku como exact-cover).
- Simonis, H. (2005). "Sudoku as a Constraint Problem". *CP Workshop on Modeling and Reformulating CSPs*. (consultar por título; el evento no asigna DOI).
