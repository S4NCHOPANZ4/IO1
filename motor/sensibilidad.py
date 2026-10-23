"""Análisis de sensibilidad desde la base óptima: precios sombra, costos reducidos y rangos."""
from fractions import Fraction

from .modelo import fmt, moneda


def _inversa(M):
    """Inversa por Gauss-Jordan con fracciones."""
    m = len(M)
    A = [list(f) + [Fraction(int(i == j)) for j in range(m)] for i, f in enumerate(M)]
    for c in range(m):
        piv = next((i for i in range(c, m) if A[i][c] != 0), None)
        if piv is None:
            raise ValueError("matriz singular")
        A[c], A[piv] = A[piv], A[c]
        A[c] = [v / A[c][c] for v in A[c]]
        for i in range(m):
            if i != c and A[i][c] != 0:
                f = A[i][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[c])]
    return [f[m:] for f in A]


def _rango_columnas(A, cols):
    """Rango de las columnas elegidas (eliminación con fracciones)."""
    M = [[A[i][j] for j in cols] for i in range(len(A))]
    r = 0
    for c in range(len(cols)):
        piv = next((i for i in range(r, len(M)) if M[i][c] != 0), None)
        if piv is None:
            continue
        M[r], M[piv] = M[piv], M[r]
        for i in range(len(M)):
            if i != r and M[i][c] != 0:
                f = M[i][c] / M[r][c]
                M[i] = [a - f * b for a, b in zip(M[i], M[r])]
        r += 1
    return r


def _reparar_base(A, b, c, base, es_max):
    """Si una artificial quedó en la base con valor 0, la reemplaza por columnas reales y termina con
    el simplex (reglas de Bland). La solución no cambia. Devuelve None si una restricción es redundante."""
    m, N = len(A), len(c)
    nueva = [j for j in base if j < N]
    for j in range(N):
        if len(nueva) == m:
            break
        if j not in nueva and _rango_columnas(A, nueva + [j]) == len(nueva) + 1:
            nueva.append(j)
    if len(nueva) < m:
        return None
    for _ in range(200):
        Bi = _inversa([[A[i][j] for j in nueva] for i in range(m)])
        y = [sum(c[nueva[k]] * Bi[k][i] for k in range(m)) for i in range(m)]
        d = [c[j] - sum(y[i] * A[i][j] for i in range(m)) for j in range(N)]
        cand = [j for j in range(N) if j not in nueva and (d[j] > 0 if es_max else d[j] < 0)]
        if not cand:
            return nueva
        e = cand[0]
        col = [sum(Bi[k][i] * A[i][e] for i in range(m)) for k in range(m)]
        xB = [sum(Bi[k][i] * b[i] for i in range(m)) for k in range(m)]
        razones = [(xB[k] / col[k], nueva[k], k) for k in range(m) if col[k] > 0]
        if not razones:
            return None
        nueva[min(razones)[2]] = e
    return None


def _rango(lo_hi_pares, centro):
    """Convierte restricciones sobre Δ en (centro+lo, centro+hi); None = infinito."""
    lo = max((v for t, v in lo_hi_pares if t == "lo"), default=None)
    hi = min((v for t, v in lo_hi_pares if t == "hi"), default=None)
    return (None if lo is None else centro + lo), (None if hi is None else centro + hi)


def analizar(p, est):
    A, b, c, base, vol = est["A"], est["b"], est["c"], est["base"], est["volteadas"]
    m, N, n = len(A), len(c), len(p.c)
    es_max = p.tipo == "max"
    if any(j >= N for j in base):
        base = _reparar_base(A, b, c, base, es_max)
        if base is None:
            return None  # restricción redundante: no hay base completa de variables reales
    Bi = _inversa([[A[i][j] for j in base] for i in range(m)])
    xB = [sum(Bi[k][i] * b[i] for i in range(m)) for k in range(m)]
    y = [sum(c[base[k]] * Bi[k][i] for k in range(m)) for i in range(m)]
    d = [c[j] - sum(y[i] * A[i][j] for i in range(m)) for j in range(N)]
    alfa = lambda k, j: sum(Bi[k][i] * A[i][j] for i in range(m))
    x = [Fraction(0)] * n
    for k, j in enumerate(base):
        if j < n:
            x[j] = xB[k]
    uz = p.unidad_z
    sufz = f" {uz}" if uz else ""

    precios = []
    for i, r in enumerate(p.restr):
        sg = -1 if vol[i] else 1
        precio = sg * y[i]
        ax = sum(r.a[j] * x[j] for j in range(n))
        holgura = r.b - ax if r.signo == "<=" else ax - r.b if r.signo == ">=" else Fraction(0)
        cond = []
        for k in range(m):
            col = sg * Bi[k][i]
            if col > 0:
                cond.append(("lo", -xB[k] / col))
            elif col < 0:
                cond.append(("hi", -xB[k] / col))
        lo, hi = _rango(cond, r.b)
        u = f" {r.unidad}" if r.unidad else ""
        rango = f"{fmt(lo) if lo is not None else '−∞'} y {fmt(hi) if hi is not None else '∞'}{u}"
        if r.signo == "=" or holgura == 0:
            if precio != 0:
                verbo = "aumenta" if precio > 0 else "reduce"
                par = f" ({r.unidad})" if r.unidad else ""
                frase = (f"Cada unidad adicional de «{r.nombre}»{par} {verbo} {p.nombre_z} en {moneda(abs(precio))}{sufz}, "
                         f"mientras el valor se mantenga entre {rango}. Esta restricción limita la decisión.")
            else:
                frase = (f"«{r.nombre}» está al límite pero su precio sombra es 0: cambiarla no modifica {p.nombre_z} "
                         f"(señal de degeneración).")
        else:
            frase = (f"«{r.nombre}» tiene una holgura de {fmt(holgura)}{u}: no limita la decisión. "
                     f"Puede moverse entre {rango} sin cambiar la solución.")
        precios.append({"nombre": r.nombre, "unidad": r.unidad, "b": r.b, "precio": precio, "holgura": holgura,
                        "lo": lo, "hi": hi, "frase": frase, "comprobacion": None})

    cj = []
    for j in range(n):
        if j in base:
            k = base.index(j)
            cond = []
            for jj in range(N):
                if jj in base:
                    continue
                al = alfa(k, jj)
                if al == 0:
                    continue
                t = d[jj] / al
                # mínimo: Δ·α <= d_j ; máximo: Δ·α >= d_j
                if (al > 0) != es_max:
                    cond.append(("hi", t))
                else:
                    cond.append(("lo", t))
            lo, hi = _rango(cond, p.c[j])
        else:
            lo, hi = (None, p.c[j] - d[j]) if es_max else (p.c[j] - d[j], None)
        rango = f"{fmt(lo) if lo is not None else '−∞'} y {fmt(hi) if hi is not None else '∞'}"
        frase = (f"El coeficiente de «{p.nombres[j]}» puede variar entre {rango} sin que cambie la solución óptima "
                 f"(las cantidades), aunque sí cambiaría el valor de {p.nombre_z}.")
        if j not in base:
            frase = (f"«{p.nombres[j]}» no se usa en la solución. Su coeficiente puede variar entre {rango} "
                     f"sin que empiece a usarse; su costo reducido es {fmt(d[j])}.")
        cj.append({"nombre": p.nombres[j], "unidad": p.unidades[j], "c": p.c[j], "lo": lo, "hi": hi,
                   "reducido": d[j], "valor": x[j], "frase": frase})

    avisos = []
    if any(f["lo"] is None or f["hi"] is None for f in precios + cj):
        avisos.append(("warn", "Hay rangos infinitos: ese dato puede crecer o decrecer sin límite sin cambiar la solución."))
    if any(f["holgura"] == 0 for f in precios):
        avisos.append(("warn", "Hay restricciones sin holgura: están al límite en la solución óptima."))
    return {"precios": precios, "cj": cj, "avisos": avisos}
