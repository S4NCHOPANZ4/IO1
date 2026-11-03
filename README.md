# Optimizador de PL · Grupo 5 (IO1-82)

App web en Flask que resuelve problemas de programación lineal con el **método gráfico** (2 variables) y la **Gran M** (hasta 8 variables × 8 restricciones, con ≤, ≥ y =). Los dos métodos están programados desde cero con fracciones exactas de Python (`fractions.Fraction`), así que no hay errores de redondeo. No usan SciPy ni otras librerías de optimización. También calcula precios sombra y rangos de sensibilidad.

## Ejecutar

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000. Los ejemplos están en el menú lateral.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

SciPy se usa solo en las pruebas, para comparar resultados. Si no está instalado, esas comparaciones se omiten.

## Cómo funcionan los métodos

Ambos resuelven: optimizar `z = c1·x1 + … + cn·xn` sujeto a restricciones `a·x {≤, ≥, =} b` con `x ≥ 0`. Cada paso del algoritmo está marcado en el código con un comentario `# Paso N`.

### Método gráfico: `motor/grafico.py`

**Idea.** Si hay un óptimo, está en un vértice de la región factible. Se calculan todos los vértices y se compara z en cada uno.

| Paso | Qué hace | Dónde |
|---|---|---|
| 1 | Convierte cada restricción y los ejes `x1 = 0`, `x2 = 0` en rectas `a1·x1 + a2·x2 = b` | `_rectas()` |
| 2 | Intersecta cada par de rectas (regla de Cramer) y obtiene los vértices candidatos | `resolver()` |
| 3 | Descarta los puntos que incumplen alguna restricción; los que quedan son los vértices | `_cumple()` |
| 4 | Evalúa z en cada vértice y escoge el menor (minimizar) o el mayor (maximizar) | `resolver()` |

Los vértices se rotulan A, B, C… de izquierda a derecha.

**Casos especiales que avisa:**

- **Infactible:** ningún punto cumple todas las restricciones, así que no hay vértices.
- **No acotado:** revisa las direcciones en las que la región podría abrirse (los ejes y la dirección de cada recta). Si alguna es válida y mejora z, no hay óptimo finito.
- **Óptimos alternativos:** dos vértices tienen el mismo z, o hay una dirección válida que no cambia z.
- **Degeneración:** en un vértice se cruzan más de dos rectas.

**Gráfica y comprobación.** `dibujar()` genera la imagen con matplotlib: una recta por restricción, la región factible sombreada, los vértices con su letra, el óptimo marcado con una estrella y la recta de z óptimo. `comprobar_precios()` verifica cada precio sombra: cambia un poco el lado derecho `b`, vuelve a resolver en el gráfico y compara Δz/Δb.

### Método de la Gran M: `motor/gran_m.py`

**Idea.** Es el simplex para problemas con restricciones ≥ y =, que no tienen una solución inicial obvia. Se agregan variables artificiales con un costo `M` tan grande que el método las saca de la base. M se maneja como símbolo, no como un número grande: la clase `MNum` (en `modelo.py`) representa números `a + b·M` y los compara primero por la parte con M.

| Paso | Qué hace |
|---|---|
| 1 | Forma estándar con todos los `b ≥ 0`. Si un `b` es negativo, se multiplica la fila por −1 y se invierte el signo |
| 2 | Las `≤` reciben una holgura `s`. Las `≥` reciben un exceso `s` y una artificial `A`. Las `=` reciben solo la artificial. El orden de columnas es `x`, `s`, `A` |
| 3 | Cada artificial entra a z con costo `+M` si se minimiza y `−M` si se maximiza |
| 4 | Calcula `cj − zj` de cada columna |
| 4b | **Factibilidad.** Si queda una artificial positiva y ninguna columna mejora ya la parte con M, el problema es infactible |
| 5 | Entra la variable con el `cj − zj` más favorable. Sale la fila de menor razón `bi/aik` (con `aik > 0`). Se pivotea con Gauss-Jordan |

El método termina cuando ningún `cj − zj` mejora. Si hay muchas iteraciones, pasa a la regla de Bland para evitar ciclos.

**Casos especiales que avisa:**

- **Infactible:** una artificial sigue en la base con valor mayor que 0 (paso 4b).
- **No acotado:** entra una variable pero su columna no tiene ningún coeficiente positivo.
- **Óptimos alternativos:** una variable no básica tiene `cj − zj = 0` en la tabla final.
- **Degeneración:** hubo un empate en la razón mínima o una variable básica vale 0.

**Qué muestra.** Una tabla por iteración con la M visible, las variables que entran y salen, el pivote resaltado y la columna de razones. Al final muestra la solución con los nombres y unidades del problema.

**Ejemplo (caso de la dieta).** Son 5 tablas: entra `x2` y sale `s4`; entra `x1` y sale `A1`; entra `s1` y sale `A2`; entra `s4` y sale `s1`; la quinta ya es óptima. El resultado es `x1 = 21,33`, `x2 = 0,64` y `z = 14.859,80`, el mismo vértice B del método gráfico.

### Sensibilidad: `motor/sensibilidad.py`

Se calcula desde la base óptima de la Gran M y se muestra en las dos pantallas de resultado: precio sombra y holgura de cada restricción, rango de cada `bi`, costo reducido y rango de cada `cj`, con una frase de interpretación. Cada rango vale solo si se cambia un dato a la vez.

## Carpetas

- `motor/`: los métodos y la sensibilidad
- `templates/` y `public/`: páginas y estilos
- `ejemplos/`: problemas en JSON
- `tests/`: pruebas automáticas