"""Pruebas de corrección: el motor se compara contra respuestas conocidas (libros de texto),
contra un oráculo propio por enumeración de vértices, contra propiedades matemáticas
(factibilidad, dualidad, invariantes de la tabla) y contra SciPy, que se usa SOLO aquí, aparte del motor."""
import itertools
import os
import random
import sys
from dataclasses import replace
from fractions import Fraction as F

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from motor import grafico, gran_m, sensibilidad
from motor.modelo import MNum, Problema, Restriccion, a_fraccion, fmt, moneda
from motor.validacion import MAX_N, completar, datos_vacios, parsear, redimensionar

try:
    from scipy.optimize import linprog
except ImportError:  # SciPy solo es una verificación extra
    linprog = None


# ---------------------------------------------------------------- utilidades
def P(tipo, c, rs, nz="z", uz="u"):
    n = len(c)
    return Problema(tipo, nz, uz, tuple(f"x{j+1}" for j in range(n)), ("",) * n, tuple(F(v) for v in c),
                    tuple(Restriccion(f"R{i+1}", "", tuple(F(v) for v in a), s, F(b)) for i, (a, s, b) in enumerate(rs)))


def con_b(p, i, nb):
    return replace(p, restr=tuple(replace(r, b=nb) if k == i else r for k, r in enumerate(p.restr)))


def con_c(p, j, nc):
    return replace(p, c=tuple(nc if k == j else v for k, v in enumerate(p.c)))


def cumple(p, x):
    for r in p.restr:
        v = sum(a * xi for a, xi in zip(r.a, x))
        if (r.signo == "<=" and v > r.b) or (r.signo == ">=" and v < r.b) or (r.signo == "=" and v != r.b):
            return False
    return all(xi >= 0 for xi in x)


def gauss(A, b):
    n = len(A)
    M = [list(f) + [v] for f, v in zip(A, b)]
    for c in range(n):
        piv = next((i for i in range(c, n) if M[i][c] != 0), None)
        if piv is None:
            return None
        M[c], M[piv] = M[piv], M[c]
        M[c] = [v / M[c][c] for v in M[c]]
        for i in range(n):
            if i != c and M[i][c] != 0:
                f = M[i][c]
                M[i] = [a - f * b for a, b in zip(M[i], M[c])]
    return [M[i][n] for i in range(n)]


def oraculo(p):
    """Enumera todos los vértices (problemas ACOTADOS). Devuelve ('optimo', z) o ('infactible', None)."""
    n = len(p.c)
    lineas = [(list(r.a), r.b) for r in p.restr] + [([F(int(i == j)) for i in range(n)], F(0)) for j in range(n)]
    mejor = None
    for comb in itertools.combinations(range(len(lineas)), n):
        x = gauss([lineas[i][0] for i in comb], [lineas[i][1] for i in comb])
        if x is not None and cumple(p, x):
            z = sum(c * v for c, v in zip(p.c, x))
            if mejor is None or (z > mejor if p.tipo == "max" else z < mejor):
                mejor = z
    return ("infactible", None) if mejor is None else ("optimo", mejor)


def aleatorio(rng, n, m, caja=True):
    c = [rng.randint(-5, 5) for _ in range(n)]
    if not any(c):
        c[0] = 1
    rs = []
    for _ in range(m):
        a = [rng.randint(-4, 5) for _ in range(n)]
        if not any(a):
            a[0] = 1
        rs.append((a, rng.choice(["<=", "<=", ">=", ">=", "="]), rng.randint(-6, 20)))
    if caja:
        rs += [([int(i == j) for i in range(n)], "<=", 30) for j in range(n)]
    return P(rng.choice(["max", "min"]), c, rs)


def scipy_estado(p):
    sg = -1 if p.tipo == "max" else 1
    Aub, bub, Aeq, beq = [], [], [], []
    for r in p.restr:
        a = [float(v) for v in r.a]
        if r.signo == "=":
            Aeq.append(a); beq.append(float(r.b))
        elif r.signo == "<=":
            Aub.append(a); bub.append(float(r.b))
        else:
            Aub.append([-v for v in a]); bub.append(-float(r.b))
    args = dict(A_ub=Aub or None, b_ub=bub or None, A_eq=Aeq or None, b_eq=beq or None, bounds=(0, None), method="highs")
    res = linprog([sg * float(v) for v in p.c], **args)
    if res.status == 2:   # HiGHS con presolve responde "infactible o no acotado": se repite sin presolve para distinguirlos
        res = linprog([sg * float(v) for v in p.c], options={"presolve": False}, **args)
    est = {0: "optimo", 2: "infactible", 3: "no_acotado"}.get(res.status, "otro")
    return est, (sg * res.fun if res.status == 0 else None)


# ------------------------------------------------- 1. respuestas conocidas
def test_wyndor_glass_hillier():
    """Hillier & Lieberman: max 3x1+5x2, x1<=4, 2x2<=12, 3x1+2x2<=18 -> (2,6), z=36."""
    p = P("max", [3, 5], [([1, 0], "<=", 4), ([0, 2], "<=", 12), ([3, 2], "<=", 18)])
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert g["z"] == m["z"] == 36 and m["x"] == [2, 6]
    s = sensibilidad.analizar(p, m["estandar"])
    assert [f["precio"] for f in s["precios"]] == [0, F(3, 2), 1]            # precios sombra conocidos
    assert (s["precios"][1]["lo"], s["precios"][1]["hi"]) == (6, 18)          # rango de b2
    assert (s["precios"][2]["lo"], s["precios"][2]["hi"]) == (12, 24)         # rango de b3
    assert (s["cj"][0]["lo"], s["cj"][0]["hi"]) == (0, F(15, 2))              # rango de c1
    assert (s["cj"][1]["lo"], s["cj"][1]["hi"]) == (2, None)                  # rango de c2


def test_minimizacion_con_mayor_igual():
    """min 2x1+3x2, x1+x2>=4, x1+3x2>=6 -> (3,1), z=9; duales 3/2 y 1/2."""
    p = P("min", [2, 3], [([1, 1], ">=", 4), ([1, 3], ">=", 6)])
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert g["z"] == m["z"] == 9 and m["x"] == [3, 1]
    s = sensibilidad.analizar(p, m["estandar"])
    assert [f["precio"] for f in s["precios"]] == [F(3, 2), F(1, 2)]


def test_rhs_negativo_invierte_signo_y_precio_sombra():
    """-x1-x2 <= -4 equivale a x1+x2 >= 4: misma solución, precio sombra con signo opuesto."""
    a = P("min", [2, 3], [([1, 1], ">=", 4), ([1, 3], ">=", 6)])
    b = P("min", [2, 3], [([-1, -1], "<=", -4), ([1, 3], ">=", 6)])
    ma, mb = gran_m.resolver(a), gran_m.resolver(b)
    assert ma["x"] == mb["x"] and ma["z"] == mb["z"]
    pa = sensibilidad.analizar(a, ma["estandar"])["precios"][0]
    pb = sensibilidad.analizar(b, mb["estandar"])["precios"][0]
    assert pb["precio"] == -pa["precio"]
    assert (pb["lo"], pb["hi"]) == (-pa["hi"], -pa["lo"]) if pa["hi"] is not None else True


def test_restriccion_de_igualdad_y_alternativos():
    p = P("max", [1, 1], [([1, 1], "=", 5), ([1, 0], "<=", 3)])
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert g["z"] == m["z"] == 5 and cumple(p, m["x"])
    assert any("alternativos" in t for _, t in g["avisos"]) and any("alternativos" in t for _, t in m["avisos"])


def test_alternativos_por_rayo_infinito():
    """min x1 con x1+x2>=3: z=0 en x1=0 para todo x2>=3 (borde sin límite)."""
    p = P("min", [1, 0], [([1, 1], ">=", 3)])
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert g["estado"] == m["estado"] == "optimo" and g["z"] == m["z"] == 0
    assert any("alternativos" in t for _, t in g["avisos"]) and any("alternativos" in t for _, t in m["avisos"])


def test_degeneracion_detectada():
    p = P("max", [1, 1], [([1, 0], "<=", 2), ([0, 1], "<=", 2), ([1, 1], "<=", 4)])
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert g["z"] == m["z"] == 4
    assert any("Degeneración" in t for _, t in g["avisos"]) and any("Degeneración" in t for _, t in m["avisos"])


def test_no_acotado_con_mayor_igual_y_minimizacion_acotada():
    p = P("max", [1, 0], [([1, -1], ">=", 1)])
    assert grafico.resolver(p)["estado"] == gran_m.resolver(p)["estado"] == "no_acotado"
    q = P("min", [1, 1], [([1, -1], "<=", 2)])      # región abierta, pero el mínimo existe (0,0)
    assert grafico.resolver(q)["z"] == gran_m.resolver(q)["z"] == 0


def test_infactible_con_igualdades():
    p = P("min", [1, 1], [([1, 1], "=", 2), ([1, 1], "=", 3)])
    assert grafico.resolver(p)["estado"] == gran_m.resolver(p)["estado"] == "infactible"


# ------------------------------------------ 2. el caso real (informe, Tablas 3-5)
def caso_real():
    return P("min", ["600", "3200"], [(["0.027625", "0.4004"], ">=", "0.847"), (["0.325", "0.88"], ">=", "7.5"),
                                      (["0.325", "0.88"], "<=", "8.5"), (["-0.04875", "0.748"], "<=", "0")],
             nz="Costo", uz="COP/día")


def test_caso_real_sensibilidad_coincide_con_informe():
    p = caso_real()
    s = sensibilidad.analizar(p, gran_m.resolver(p)["estandar"])
    pr, cj = s["precios"], s["cj"]
    cerca = lambda a, b: abs(float(a) - b) < 0.01
    assert cerca(pr[0]["precio"], 4838.40) and cerca(pr[1]["precio"], 1434.89)
    assert pr[2]["precio"] == 0 and pr[3]["precio"] == 0
    assert cerca(pr[0]["lo"], 0.6375) and cerca(pr[0]["hi"], 1.0537)
    assert cerca(pr[1]["lo"], 6.0285) and pr[1]["hi"] == F(17, 2)
    assert pr[2]["lo"] == F(15, 2) and pr[2]["hi"] is None and cerca(pr[3]["lo"], -0.559)
    assert cerca(cj[0]["lo"], 220.78) and cerca(cj[0]["hi"], 1181.82)
    assert cerca(cj[1]["lo"], 1624.62) and cerca(cj[1]["hi"], 8696.47)


def test_caso_real_fuera_del_rango_cambia_la_solucion():
    p = caso_real()
    m = gran_m.resolver(p)
    s = sensibilidad.analizar(p, m["estandar"])
    dentro = gran_m.resolver(con_c(p, 0, F(1100)))
    fuera = gran_m.resolver(con_c(p, 0, F(1200)))     # 1200 > 1181,82
    assert dentro["x"] == m["x"] and fuera["x"] != m["x"]
    assert float(s["cj"][0]["hi"]) < 1200


def test_comprobacion_grafica_de_precios_sombra():
    p = caso_real()
    g = grafico.resolver(p)
    s = sensibilidad.analizar(p, gran_m.resolver(p)["estandar"])
    grafico.comprobar_precios(p, g, s)
    chequeados = [f["comprobacion"] for f in s["precios"] if f["comprobacion"]]
    assert len(chequeados) >= 2 and all(ok for _, ok in chequeados)


# ----------------------------------------- 3. aleatorios contra el oráculo y SciPy
def test_aleatorios_contra_oraculo():
    rng = random.Random(2026)
    vistos = {"optimo": 0, "infactible": 0}
    for _ in range(400):
        p = aleatorio(rng, rng.choice([2, 3]), rng.randint(1, 4))
        est, z = oraculo(p)
        m = gran_m.resolver(p)
        assert m["estado"] == est, (p, m["estado"], est)
        vistos[est] += 1
        if est == "optimo":
            assert m["z"] == z, p
            assert cumple(p, m["x"]) and sum(c * v for c, v in zip(p.c, m["x"])) == z
        if len(p.c) == 2:
            g = grafico.resolver(p)
            assert g["estado"] == est and (est != "optimo" or g["z"] == z), p
    assert vistos["optimo"] > 40 and vistos["infactible"] > 40     # la muestra cubre ambos casos


def test_aleatorios_sin_caja_contra_scipy():
    """Incluye problemas no acotados: ambos métodos y SciPy deben dar el mismo estado y z."""
    if linprog is None:
        return
    rng = random.Random(7)
    vistos = {"optimo": 0, "infactible": 0, "no_acotado": 0}
    for _ in range(300):
        p = aleatorio(rng, 2, rng.randint(1, 5), caja=False)
        est, z = scipy_estado(p)
        g, m = grafico.resolver(p), gran_m.resolver(p)
        assert g["estado"] == est and m["estado"] == est, (p, est, g["estado"], m["estado"])
        vistos[est] += 1
        if est == "optimo":
            assert abs(float(g["z"]) - z) < 1e-6 and abs(float(m["z"]) - z) < 1e-6
    assert all(v > 15 for v in vistos.values()), vistos


def test_tamano_maximo_8x8_contra_scipy():
    rng = random.Random(11)
    for _ in range(10):
        c = [rng.randint(1, 9) for _ in range(8)]
        rs = [([rng.randint(1, 9) for _ in range(8)], "<=", rng.randint(40, 100)) for _ in range(8)]
        p = P("max", c, rs)
        m = gran_m.resolver(p)
        assert m["estado"] == "optimo" and cumple(p, m["x"])
        if linprog is not None:
            assert abs(float(m["z"]) - scipy_estado(p)[1]) < 1e-6


# ---------------------------------------------- 4. invariantes de las tablas
def test_invariantes_de_cada_tabla_gran_m():
    rng = random.Random(5)
    revisadas = 0
    for _ in range(150):
        p = aleatorio(rng, 3, rng.randint(2, 4))
        m = gran_m.resolver(p)
        zs = [t["z"] for t in m["tablas"]]
        for t in m["tablas"]:
            assert all(v >= 0 for v in t["b"])                                  # b >= 0 siempre
            for i, nombre in enumerate(t["base"]):                              # la base es una identidad
                j = m["nombres"].index(nombre)
                assert [f[j] for f in t["filas"]] == [int(k == i) for k in range(len(t["filas"]))]
        for a, b in zip(zs, zs[1:]):                                            # z nunca empeora
            assert (b >= a) if p.tipo == "max" else (b <= a)
        revisadas += len(m["tablas"])
    assert revisadas > 300


def test_identidad_de_dualidad_z_igual_suma_precio_por_b():
    rng = random.Random(3)
    comprobados = 0
    for _ in range(300):
        p = aleatorio(rng, rng.choice([2, 3]), rng.randint(1, 4))
        m = gran_m.resolver(p)
        if m["estado"] != "optimo":
            continue
        s = sensibilidad.analizar(p, m["estandar"])
        if s is None:
            continue
        assert sum(f["precio"] * f["b"] for f in s["precios"]) == m["z"]
        assert all((f["reducido"] >= 0) if p.tipo == "min" else (f["reducido"] <= 0) for f in s["cj"])
        comprobados += 1
    assert comprobados > 60


# ------------------------------------------- 5. sensibilidad por re-resolución
def test_sensibilidad_aleatoria_por_perturbacion():
    """Precio sombra = Δz/Δb y z lineal hasta los extremos del rango; el rango de c_j conserva el óptimo."""
    rng = random.Random(99)
    comprobados = 0
    for _ in range(250):
        p = aleatorio(rng, rng.choice([2, 3]), rng.randint(1, 4))
        m = gran_m.resolver(p)
        if m["estado"] != "optimo":
            continue
        s = sensibilidad.analizar(p, m["estandar"])
        if s is None:
            continue
        for i, f in enumerate(s["precios"]):
            for nb in [x for x in (f["lo"], f["hi"], f["b"] + F(1, 1000), f["b"] - F(1, 1000)) if x is not None]:
                if (f["lo"] is not None and nb < f["lo"]) or (f["hi"] is not None and nb > f["hi"]):
                    continue
                n2 = gran_m.resolver(con_b(p, i, nb))
                assert n2["estado"] == "optimo" and n2["z"] == m["z"] + f["precio"] * (nb - f["b"]), (p, i, nb)
                comprobados += 1
        for j, f in enumerate(s["cj"]):
            for nc in [x for x in (f["lo"], f["hi"]) if x is not None]:
                n2 = gran_m.resolver(con_c(p, j, nc))
                nuevo = [v if k != j else nc for k, v in enumerate(p.c)]
                assert n2["estado"] == "optimo"
                assert n2["z"] == sum(c * x for c, x in zip(nuevo, m["x"])), (p, j, nc)   # x sigue siendo óptimo
                comprobados += 1
    assert comprobados > 300


# ------------------------------------------------- 6. interpretación (frases)
def test_frases_del_caso_real():
    p = caso_real()
    s = sensibilidad.analizar(p, gran_m.resolver(p)["estandar"])
    f0, f2 = s["precios"][0]["frase"], s["precios"][2]["frase"]
    assert "R1" in f0 and "aumenta Costo en 4.838,40 COP/día" in f0 and "0,6375 y 1,0537" in f0 and "limita la decisión" in f0
    assert "holgura de 1" in f2 and "no limita" in f2
    assert "x1" in s["cj"][0]["frase"] and "220,7792 y 1181,8182" in s["cj"][0]["frase"]
    textos = [t for _, t in s["avisos"]]
    assert any("sin holgura" in t for t in textos) and any("infinitos" in t for t in textos)


def test_frase_indica_si_z_aumenta_o_se_reduce():
    mx = P("max", [3, 5], [([1, 0], "<=", 4), ([0, 2], "<=", 12), ([3, 2], "<=", 18)], nz="Ganancia", uz="miles")
    s = sensibilidad.analizar(mx, gran_m.resolver(mx)["estandar"])
    assert "aumenta Ganancia en 1,50 miles" in s["precios"][1]["frase"]
    b = P("min", [2, 3], [([-1, -1], "<=", -4), ([1, 3], ">=", 6)], nz="Costo", uz="$")
    f = sensibilidad.analizar(b, gran_m.resolver(b)["estandar"])["precios"][0]["frase"]
    assert "reduce Costo en 1,50 $" in f           # fila con b<0: relajar la restricción abarata


def test_frase_de_variable_que_no_se_usa():
    p = P("max", [3, 1], [([1, 1], "<=", 4)])     # solo x1 entra: x2 queda en 0
    s = sensibilidad.analizar(p, gran_m.resolver(p)["estandar"])
    assert "no se usa" in s["cj"][1]["frase"] and s["cj"][1]["valor"] == 0


def test_no_hay_sensibilidad_si_no_hay_optimo():
    p = P("max", [1, 1], [([1, 1], "<=", 4), ([1, 1], ">=", 6)])
    m = gran_m.resolver(p)
    assert m["estado"] == "infactible" and m["z"] is None and m["avisos"][0][0] == "error"


# ------------------------------------------------- 7. formato y números
def test_formato_de_numeros():
    assert fmt(F(1, 3)) == "0,3333" and fmt(5) == "5" and fmt(F(-5, 2)) == "-2,5" and fmt(F(1, 100000)) == "0"
    assert fmt(MNum(0, 1)) == "M" and fmt(MNum(0, -1)) == "-M" and fmt(MNum(600, F(-3526, 10000))) == "600 - 0,3526M"
    assert fmt(MNum(8, 2)) == "8 + 2M"
    assert moneda(14859.8) == "14.859,80" and moneda(0) == "0,00" and moneda(-1234.5) == "-1.234,50"


def test_orden_de_M():
    assert MNum(0, 1) > MNum(10**9, 0) and MNum(5, 1) > MNum(3, 1) and MNum(0, -1) < MNum(-10**9, 0)
    assert MNum(1, 1) - MNum(1, 1) == MNum(0, 0)


def test_lectura_de_numeros():
    assert a_fraccion("0,5") == F(1, 2) and a_fraccion(" -2.25 ") == F(-9, 4) and a_fraccion("1/3") == F(1, 3)
    for malo in ["", "  ", "abc", "1e5", "inf", "nan", "1/0", "1_0", "12,3,4", "9" * 30]:
        try:
            a_fraccion(malo)
        except ValueError:
            continue
        raise AssertionError(f"debió rechazar {malo!r}")


# ------------------------------------------------- 8. validación
def datos_ok():
    d = datos_vacios("gran_m", "max", 2, 1)
    d["vars"] = [{"nombre": "A", "unidad": "u", "c": "1"}, {"nombre": "B", "unidad": "u", "c": "2"}]
    d["restr"] = [{"nombre": "R", "unidad": "h", "a": ["1", "1"], "signo": "<=", "b": "4"}]
    return d


def test_validacion_casos():
    p, err = parsear(datos_ok())
    assert p is not None and not err and p.nombres == ("A", "B")
    d = datos_ok(); d["metodo"] = "grafico"; d["n"] = 3; d["vars"].append({"nombre": "", "unidad": "", "c": "1"})
    d["restr"][0]["a"].append("1")
    assert "2 variables" in parsear(d)[1][0]                       # gráfico solo con 2 variables
    d = datos_ok(); d["n"] = MAX_N + 1
    assert parsear(d)[0] is None                                    # más de 8
    d = datos_ok(); d["restr"][0]["signo"] = "<>"
    assert "signo" in parsear(d)[1][0]
    d = datos_ok(); d["vars"] = [{"nombre": "", "unidad": "", "c": "0"}] * 2
    assert "cero" in parsear(d)[1][0]
    d = datos_ok(); d["tipo"] = "otro"
    assert parsear(d)[0] is None


def test_redimensionar_conserva_datos():
    d = completar({"n": 2, "m": 1, **{k: v for k, v in datos_ok().items() if k in ("vars", "restr", "nombre_z", "unidad_z")}})
    mas = redimensionar(d, 3, 2)
    assert mas["vars"][1]["c"] == "2" and mas["restr"][0]["a"] == ["1", "1", ""] and len(mas["restr"]) == 2
    menos = redimensionar(mas, 1, 1)
    assert menos["restr"][0]["a"] == ["1"] and len(menos["vars"]) == 1


# ------------------------------------------------- 9. aplicación web
def test_rutas_web():
    from app import app
    c = app.test_client()
    assert c.get("/").status_code == 200
    css = c.get("/estilo.css")
    assert css.status_code == 200 and b"--verde" in css.data and 'href="/estilo.css"' in c.get("/").get_data(as_text=True)
    for nombre in ["dieta", "prueba1_alternativos", "prueba2_infactible", "prueba3_no_acotado"]:
        assert c.get(f"/ejemplo/{nombre}").status_code == 200
    assert c.get("/ejemplo/no_existe").status_code == 404 and c.get("/ejemplo/..%2Fapp").status_code == 404


def forma(d, metodo):
    f = {"n": d["n"], "m": d["m"], "metodo": metodo, "tipo": d["tipo"], "nombre_z": d["nombre_z"], "unidad_z": d["unidad_z"]}
    for j, v in enumerate(d["vars"]):
        f.update({f"v_nombre_{j}": v["nombre"], f"v_unidad_{j}": v["unidad"], f"c_{j}": v["c"]})
    for i, r in enumerate(d["restr"]):
        f.update({f"r_nombre_{i}": r["nombre"], f"r_unidad_{i}": r["unidad"], f"s_{i}": r["signo"], f"b_{i}": r["b"]})
        f.update({f"a_{i}_{j}": a for j, a in enumerate(r["a"])})
    return f


def test_resultados_web_de_cada_ejemplo():
    import json
    from app import app
    c = app.test_client()
    esperado = {"dieta": "14.859,80", "prueba1_alternativos": "16,00", "prueba2_infactible": "infactible",
                "prueba3_no_acotado": "no acotado"}
    for nombre, texto in esperado.items():
        with open(os.path.join(os.path.dirname(__file__), "..", "ejemplos", nombre + ".json"), encoding="utf-8") as fh:
            d = completar(json.load(fh))
        for metodo in ("grafico", "gran_m"):
            r = c.post("/resolver", data=forma(d, metodo))
            html = r.get_data(as_text=True)
            assert r.status_code == 200 and texto.lower() in html.lower(), (nombre, metodo)
            assert ("data:image/png" in html) == (metodo == "grafico")


def test_web_mantiene_datos_si_hay_error():
    import json
    from app import app
    with open(os.path.join(os.path.dirname(__file__), "..", "ejemplos", "dieta.json"), encoding="utf-8") as fh:
        d = completar(json.load(fh))
    f = forma(d, "gran_m"); f["b_0"] = ""; f["c_1"] = "hola"
    html = app.test_client().post("/resolver", data=f).get_data(as_text=True)
    assert "Revisa estos datos" in html and "hola" in html and 'value="7,5"' in html and "Traceback" not in html
