"""Método gráfico (2 variables): rectas, vértices, óptimo y casos especiales."""
import base64
import io
from dataclasses import replace
from fractions import Fraction

COLORES = ["#4cc9f0", "#f4a261", "#f472b6", "#a78bfa", "#facc15", "#2dd4bf", "#fb7185", "#93c5fd"]


def _cumple(r, x, y):
    v = r.a[0] * x + r.a[1] * y
    return v <= r.b if r.signo == "<=" else v >= r.b if r.signo == ">=" else v == r.b


def _rectas(p):
    """Paso 1: cada restricción y los dos ejes como rectas a1·x + a2·y = b."""
    rs = [(r.a[0], r.a[1], r.b, r.nombre) for r in p.restr]
    cero, uno = Fraction(0), Fraction(1)
    return rs + [(uno, cero, cero, f"{p.nombres[0]} ≥ 0"), (cero, uno, cero, f"{p.nombres[1]} ≥ 0")]


def resolver(p):
    c1, c2 = p.c
    rectas = _rectas(p)
    puntos = set()
    # Paso 2: vértices candidatos = intersección de cada par de rectas.
    for i in range(len(rectas)):
        for j in range(i + 1, len(rectas)):
            a1, a2, b, _ = rectas[i]
            d1, d2, e, _ = rectas[j]
            det = a1 * d2 - a2 * d1
            if det != 0:
                puntos.add(((b * d2 - a2 * e) / det, (a1 * e - b * d1) / det))
    todos = [q for q in puntos if q[0] >= 0 and q[1] >= 0]
    # Paso 3: se descartan los que incumplen alguna restricción.
    vertices = []
    for x, y in todos:
        if x >= 0 and y >= 0 and all(_cumple(r, x, y) for r in p.restr):
            activas = [nom for a1, a2, b, nom in rectas if a1 * x + a2 * y == b]
            vertices.append({"x": x, "y": y, "z": c1 * x + c2 * y, "activas": activas})
    vertices.sort(key=lambda v: (v["x"], v["y"]))  # rótulos A, B, C... de izquierda a derecha
    for k, v in enumerate(vertices):
        v["letra"], v["optimo"] = chr(65 + k), False
    res = {"estado": None, "vertices": vertices, "optimos": [], "avisos": [], "puntos": todos, "z": None}

    if not vertices:
        res["estado"] = "infactible"
        res["avisos"].append(("error", "Problema infactible: ninguna combinación cumple todas las restricciones a la vez. "
                                       "La región factible está vacía."))
        return res

    # Direcciones en las que la región podría abrirse (ejes y direcciones de cada recta).
    dirs = [(Fraction(1), Fraction(0)), (Fraction(0), Fraction(1))]
    for r in p.restr:
        dirs += [(-r.a[1], r.a[0]), (r.a[1], -r.a[0])]

    def rayo(d):
        if d[0] < 0 or d[1] < 0:
            return False
        for r in p.restr:
            v = r.a[0] * d[0] + r.a[1] * d[1]
            if (r.signo == "<=" and v > 0) or (r.signo == ">=" and v < 0) or (r.signo == "=" and v != 0):
                return False
        return True

    rayos = [d for d in dirs if rayo(d)]
    mejora = [d for d in rayos if (c1 * d[0] + c2 * d[1] > 0) == (p.tipo == "max") and c1 * d[0] + c2 * d[1] != 0]
    if mejora:
        res["estado"] = "no_acotado"
        res["avisos"].append(("error", "Problema no acotado: la región factible se extiende sin límite en la dirección en que "
                                       "mejora la función objetivo, así que no existe un óptimo finito."))
        return res

    # Paso 4: se evalúa z en cada vértice.
    mejor = (max if p.tipo == "max" else min)(v["z"] for v in vertices)
    res["estado"], res["z"] = "optimo", mejor
    res["optimos"] = [v for v in vertices if v["z"] == mejor]
    for v in res["optimos"]:
        v["optimo"] = True
    if len(res["optimos"]) > 1 or any(c1 * d[0] + c2 * d[1] == 0 for d in rayos):
        letras = " y ".join(v["letra"] for v in res["optimos"])
        res["avisos"].append(("warn", f"Óptimos alternativos: z vale lo mismo en los vértices {letras} y en todo el borde que los une "
                                      f"(o que sigue sin límite desde ellos). Se muestra uno de ellos."))
    for v in vertices:
        if len(v["activas"]) > 2:
            res["avisos"].append(("warn", f"Degeneración: en el vértice {v['letra']} se cruzan {len(v['activas'])} rectas "
                                          f"({', '.join(v['activas'])})."))
    return res


def comprobar_precios(p, res, sens):
    """Verifica en el gráfico cada precio sombra: cambia b_i un poco, vuelve a resolver y compara Δz/Δb."""
    for fila, r in zip(sens["precios"], p.restr):
        delta = (abs(r.b) if r.b != 0 else Fraction(1)) / 100
        fila["comprobacion"] = None
        for dl in (delta, -delta):
            nb = r.b + dl
            if (fila["lo"] is not None and nb < fila["lo"]) or (fila["hi"] is not None and nb > fila["hi"]):
                continue
            q = replace(p, restr=tuple(replace(s, b=nb) if s is r else s for s in p.restr))
            nuevo = resolver(q)
            if nuevo["estado"] == "optimo":
                fila["comprobacion"] = ((nuevo["z"] - res["z"]) / dl, (nuevo["z"] - res["z"]) / dl == fila["precio"])
                break


def _t(s):
    """Escapa $ para que matplotlib no lo lea como fórmula matemática."""
    return str(s).replace("$", r"\$")


def dibujar(p, res):
    """Gráfica con tema oscuro. Devuelve PNG en base64 para incrustarlo en la página."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    pts = [(float(v["x"]), float(v["y"])) for v in res["vertices"]] or \
          [(float(x), float(y)) for x, y in res["puntos"]] or [(0.0, 0.0), (10.0, 10.0)]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    f = 1.0 if res["estado"] == "no_acotado" else 0.4
    sx, sy = max(max(xs) - min(xs), 0.25 * max(xs), 1.0), max(max(ys) - min(ys), 0.25 * max(ys), 1.0)
    xlo, xhi = max(0, min(xs) - 0.3 * sx), max(xs) + f * sx + 0.1
    ylo, yhi = max(0, min(ys) - 0.3 * sy), max(ys) + f * sy + 0.1

    fondo, panel, texto = "#121212", "#181818", "#b3b3b3"
    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=110, facecolor=panel)
    ax.set_facecolor(fondo)
    for s in ax.spines.values():
        s.set_color("#333")
    ax.tick_params(colors=texto)
    ax.grid(color="#2a2a2a", lw=0.8)

    X, Y = np.meshgrid(np.linspace(xlo, xhi, 600), np.linspace(ylo, yhi, 600))
    mask = (X >= -1e-9) & (Y >= -1e-9)
    for r in p.restr:
        v, b, tol = float(r.a[0]) * X + float(r.a[1]) * Y, float(r.b), 1e-9 * (1 + abs(float(r.b)))
        if r.signo == "<=":
            mask &= v <= b + tol
        elif r.signo == ">=":
            mask &= v >= b - tol
    if mask.any():
        ax.contourf(X, Y, mask.astype(float), levels=[0.5, 1.5], colors=["#1db954"], alpha=0.28, zorder=1)
    for k, r in enumerate(p.restr):
        a1, a2, b = float(r.a[0]), float(r.a[1]), float(r.b)
        col = COLORES[k % len(COLORES)]
        txt = _t(f"({k+1}) {r.nombre}")
        if a2 != 0:
            ax.plot([xlo, xhi], [(b - a1 * xlo) / a2, (b - a1 * xhi) / a2], color=col, lw=2, label=txt, zorder=2)
        else:
            ax.axvline(b / a1, color=col, lw=2, label=txt, zorder=2)
    if res["estado"] == "optimo":
        c1, c2, z = float(p.c[0]), float(p.c[1]), float(res["z"])
        if c2 != 0:
            ax.plot([xlo, xhi], [(z - c1 * xlo) / c2, (z - c1 * xhi) / c2], "--", color="#1ed760", lw=1.6,
                    label="Recta de z óptimo", zorder=2)
        else:
            ax.axvline(z / c1, ls="--", color="#1ed760", lw=1.6, label="Recta de z óptimo")
    for v in res["vertices"]:
        x, y = float(v["x"]), float(v["y"])
        if v["optimo"]:
            ax.plot(x, y, marker="*", ms=17, color="#1ed760", mec="white", zorder=5)
        else:
            ax.plot(x, y, "o", ms=7, color="white", zorder=4)
        ax.annotate(v["letra"], (x, y), xytext=(7, 7), textcoords="offset points", color="white",
                    fontsize=11, fontweight="bold", zorder=6)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_xlabel(_t(f"{p.nombres[0]} ({p.unidades[0]})" if p.unidades[0] else p.nombres[0]), color=texto)
    ax.set_ylabel(_t(f"{p.nombres[1]} ({p.unidades[1]})" if p.unidades[1] else p.nombres[1]), color=texto)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=True, fontsize=9)
    leg.get_frame().set_facecolor("#282828")
    leg.get_frame().set_edgecolor("#333")
    for t in leg.get_texts():
        t.set_color("white")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=panel)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()
