"""Método de la Gran M con tablas por iteración (M simbólica, fracciones exactas)."""
from fractions import Fraction

from .modelo import INVERSO, MNum, fmt

CERO, UNO = Fraction(0), Fraction(1)


def resolver(p, max_iter=200):
    n, es_max = len(p.c), p.tipo == "max"

    # Paso 1: forma estándar con todos los b_i >= 0 (si b < 0 se multiplica la fila por -1).
    filas, volteadas = [], []
    for r in p.restr:
        a, s, b, v = list(r.a), r.signo, r.b, False
        if b < 0:
            a, b, s, v = [-x for x in a], -b, INVERSO[s], True
        filas.append((a, s, b))
        volteadas.append(v)
    m = len(filas)

    # Paso 2: holgura (<=), exceso (>=) y artificiales (>= y =). Orden: x, s, A.
    nombres = [f"x{j+1}" for j in range(n)]
    hol = {}
    for i, (_, s, _) in enumerate(filas):
        if s != "=":
            nombres.append(f"s{i+1}")
            hol[i] = len(nombres) - 1
    n_std = len(nombres)
    art, k = {}, 0
    for i, (_, s, _) in enumerate(filas):
        if s != "<=":
            k += 1
            nombres.append(f"A{k}")
            art[i] = len(nombres) - 1
    N = len(nombres)

    T, base = [], []
    for i, (a, s, _) in enumerate(filas):
        fila = a + [CERO] * (N - n)
        if i in hol:
            fila[hol[i]] = UNO if s == "<=" else -UNO
        if i in art:
            fila[art[i]] = UNO
        T.append(fila)
        base.append(art[i] if i in art else hol[i])
    rhs = [f[2] for f in filas]
    estandar = {"A": [f[:n_std] for f in T], "b": list(rhs), "c": [Fraction(x) for x in p.c] + [CERO] * (n_std - n),
                "nombres": nombres[:n_std], "volteadas": volteadas}

    # Paso 3: cada artificial entra a la función objetivo con +M (min) o -M (max).
    coste = [MNum(c) for c in p.c] + [MNum(0)] * (N - n)
    for j in art.values():
        coste[j] = MNum(0, -1 if es_max else 1)

    tablas, avisos, degenerado = [], [], False
    estado = None
    it = 0
    while True:
        cb = [coste[base[i]] for i in range(m)]
        cz = []
        for j in range(N):  # Paso 4: c_j - z_j
            v = coste[j]
            for i in range(m):
                v = v - cb[i] * T[i][j]
            cz.append(v)
        z = MNum(0)
        for i in range(m):
            z = z + cb[i] * rhs[i]
        tabla = {"n": it, "base": [nombres[j] for j in base], "cb": cb, "filas": [list(f) for f in T],
                 "b": list(rhs), "cz": cz, "z": z, "entra": None, "sale": None, "pivote": None,
                 "pos": None, "razones": [None] * m}
        tablas.append(tabla)

        # Paso 4b: factibilidad. La parte con M de c_j - z_j es el costo reducido de la Fase 1.
        # Si queda una artificial positiva y ninguna columna mejora esa parte, no se puede sacar la
        # artificial de la base: el problema es infactible (y "sin fila pivote" ya no probaría que
        # sea no acotado).
        art_pos = [(nombres[base[i]], rhs[i]) for i in range(m) if nombres[base[i]][0] == "A" and rhs[i] > 0]
        if art_pos and not any(nombres[j][0] != "A" and (cz[j].m > 0 if es_max else cz[j].m < 0) for j in range(N)):
            estado = "infactible"
            avisos.append(("error", "Problema infactible: ninguna variable puede reducir ya las artificiales y "
                                    f"{art_pos[0][0]} sigue en la base con valor {fmt(art_pos[0][1])} > 0, "
                                    "así que no existe solución que cumpla todas las restricciones."))
            break

        # Paso 5: variable que entra (c_j - z_j más favorable; Bland si hay muchas iteraciones).
        cand = [j for j in range(N) if nombres[j][0] != "A" and (cz[j] > MNum(0) if es_max else cz[j] < MNum(0))]
        if not cand:
            break
        if it < 25:
            e = (max if es_max else min)(cand, key=lambda j: (cz[j], -j) if es_max else (cz[j], j))
        else:
            e = cand[0]
        razones = [rhs[i] / T[i][e] if T[i][e] > 0 else None for i in range(m)]
        validas = [r for r in razones if r is not None]
        if not validas:
            estado = "no_acotado"
            tabla["entra"] = nombres[e]
            avisos.append(("error", f"Problema no acotado: la variable {nombres[e]} puede crecer sin límite "
                                    f"porque su columna no tiene ningún coeficiente positivo."))
            break
        minimo = min(validas)
        filas_min = [i for i in range(m) if razones[i] == minimo]
        r = min(filas_min, key=lambda i: base[i])
        if len(filas_min) > 1 or minimo == 0:
            degenerado = True
        tabla.update(entra=nombres[e], sale=nombres[base[r]], pivote=T[r][e], pos=(r, e), razones=razones)
        # Pivoteo (Gauss-Jordan).
        piv = T[r][e]
        T[r] = [v / piv for v in T[r]]
        rhs[r] /= piv
        for i in range(m):
            f = T[i][e]
            if i != r and f != 0:
                T[i] = [a - f * b for a, b in zip(T[i], T[r])]
                rhs[i] -= f * rhs[r]
        base[r] = e
        it += 1
        if it > max_iter:
            estado = "error"
            avisos.append(("error", "Se superó el máximo de iteraciones."))
            break

    x = [CERO] * n
    if estado is None:
        for i, j in enumerate(base):
            if j < n:
                x[j] = rhs[i]
        estado = "optimo"
        alt = [nombres[j] for j in range(N) if j not in base and nombres[j][0] != "A" and cz[j] == MNum(0)]
        if alt:
            avisos.append(("warn", f"Óptimos alternativos: la variable no básica {', '.join(alt)} tiene c_j − z_j = 0; "
                                   f"entrar a la base da otra solución con el mismo z."))
        if degenerado or any(rhs[i] == 0 for i in range(m)):
            avisos.append(("warn", "Degeneración: hubo un empate en la razón mínima o una variable básica vale 0."))
    z_orig = sum((p.c[j] * x[j] for j in range(n)), CERO) if estado == "optimo" else None
    return {"estado": estado, "tablas": tablas, "nombres": nombres, "x": x, "z": z_orig, "avisos": avisos,
            "base": list(base), "rhs": list(rhs), "estandar": {**estandar, "base": list(base)}}
