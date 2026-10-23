"""Lectura del formulario y validación. Nunca lanza excepciones: devuelve mensajes."""
from .modelo import Problema, Restriccion, SIGNOS, a_fraccion

MAX_N = 8


def _entero(valor, defecto, lo, hi):
    try:
        return max(lo, min(hi, int(valor)))
    except (TypeError, ValueError):
        return defecto


def datos_vacios(metodo="grafico", tipo="max", n=2, m=3):
    return {
        "metodo": metodo, "tipo": tipo, "n": n, "m": m, "nombre_z": "", "unidad_z": "",
        "vars": [{"nombre": "", "unidad": "", "c": ""} for _ in range(n)],
        "restr": [{"nombre": "", "unidad": "", "a": [""] * n, "signo": "<=", "b": ""}
                  for _ in range(m)],
    }


def datos_desde_form(form):
    """Reconstruye los datos tal como los escribió el usuario (para volver a mostrarlos)."""
    n = _entero(form.get("n"), 2, 1, MAX_N)
    m = _entero(form.get("m"), 3, 1, MAX_N)
    d = datos_vacios(form.get("metodo", "grafico"), form.get("tipo", "max"), n, m)
    d["nombre_z"], d["unidad_z"] = form.get("nombre_z", ""), form.get("unidad_z", "")
    for j in range(n):
        d["vars"][j] = {"nombre": form.get(f"v_nombre_{j}", ""), "unidad": form.get(f"v_unidad_{j}", ""),
                        "c": form.get(f"c_{j}", "")}
    for i in range(m):
        d["restr"][i] = {"nombre": form.get(f"r_nombre_{i}", ""), "unidad": form.get(f"r_unidad_{i}", ""),
                         "a": [form.get(f"a_{i}_{j}", "") for j in range(n)],
                         "signo": form.get(f"s_{i}", "<="), "b": form.get(f"b_{i}", "")}
    return d


def completar(d):
    """Normaliza un ejemplo cargado desde JSON (rellena lo que falte)."""
    base = datos_vacios(d.get("metodo", "grafico"), d.get("tipo", "max"), d["n"], d["m"])
    base.update({k: d[k] for k in ("nombre_z", "unidad_z", "vars", "restr") if k in d})
    return base


def redimensionar(d, n, m):
    """Cambia el tamaño conservando lo ya escrito."""
    nuevo = datos_vacios(d["metodo"], d["tipo"], n, m)
    nuevo["nombre_z"], nuevo["unidad_z"] = d["nombre_z"], d["unidad_z"]
    for j in range(min(n, d["n"])):
        nuevo["vars"][j] = d["vars"][j]
    for i in range(min(m, d["m"])):
        r = d["restr"][i]
        nuevo["restr"][i] = {**r, "a": [r["a"][j] if j < d["n"] else "" for j in range(n)]}
    return nuevo


def parsear(d):
    """Valida los datos escritos. Devuelve (Problema | None, lista de errores)."""
    err = []
    n, m = d["n"], d["m"]
    if d["tipo"] not in ("max", "min"):
        err.append("Elige si el problema se maximiza o se minimiza.")
    if d["metodo"] not in ("grafico", "gran_m"):
        err.append("Elige un método.")
    if not (1 <= n <= MAX_N and 1 <= m <= MAX_N):
        err.append(f"El número de variables y de restricciones debe estar entre 1 y {MAX_N}.")
    if d["metodo"] == "grafico" and n != 2:
        err.append("El método gráfico solo resuelve problemas de 2 variables. "
                   "Cambia el tamaño a 2 variables o usa la Gran M.")
    if err:
        return None, err

    nombres = [(v["nombre"].strip()[:40] or f"x{j+1}") for j, v in enumerate(d["vars"])]
    unidades = [v["unidad"].strip()[:40] for v in d["vars"]]

    def num(texto, donde):
        try:
            return a_fraccion(texto)
        except ValueError:
            err.append(f"{donde}: " + ("está vacío." if not str(texto).strip()
                                       else f"«{str(texto).strip()[:20]}» no es un número."))
            return None

    c = [num(v["c"], f"Coeficiente de «{nombres[j]}» en la función objetivo") for j, v in enumerate(d["vars"])]
    restr = []
    for i, r in enumerate(d["restr"]):
        nom = r["nombre"].strip()[:40] or f"Restricción {i+1}"
        a = [num(r["a"][j], f"{nom}, coeficiente de «{nombres[j]}»") for j in range(n)]
        b = num(r["b"], f"{nom}, lado derecho")
        if r["signo"] not in SIGNOS:
            err.append(f"{nom}: signo no válido.")
        restr.append((nom, r["unidad"].strip()[:40], a, r["signo"], b))
    if all(v == 0 for v in c if v is not None) and None not in c:
        err.append("La función objetivo no puede tener todos los coeficientes en cero.")
    for nom, _, a, _, _ in restr:
        if None not in a and all(v == 0 for v in a):
            err.append(f"{nom}: todos los coeficientes son cero, la restricción no tiene sentido.")
    if err:
        return None, err
    return Problema(d["tipo"], d["nombre_z"].strip()[:40] or "z", d["unidad_z"].strip()[:40],
                    tuple(nombres), tuple(unidades), tuple(c),
                    tuple(Restriccion(nom, u, tuple(a), s, b) for nom, u, a, s, b in restr)), []
