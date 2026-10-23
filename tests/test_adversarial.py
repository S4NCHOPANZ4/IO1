"""Pruebas adversariales: casos pensados para romper el motor (ciclado, redundancia, propiedades
metamórficas, nombres raros, entradas basura). Complementan test_correccion.py."""
import json
import os
import random
import sys
from dataclasses import replace
from fractions import Fraction as F

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from motor import grafico, gran_m, sensibilidad
from motor.modelo import Restriccion
from motor.validacion import completar
from test_correccion import P, aleatorio, caso_real, con_b, con_c, forma, linprog, scipy_estado

EJ = os.path.join(os.path.dirname(__file__), "..", "ejemplos")


def test_beale_no_cicla():
    """Ejemplo clásico de ciclado con la regla de Dantzig: debe terminar con z = -5/4."""
    p = P("min", [F(-3, 4), 20, F(-1, 2), 6], [([F(1, 4), -8, -1, 9], "<=", 0), ([F(1, 2), -12, F(-1, 2), 3], "<=", 0),
                                               ([0, 0, 1, 0], "<=", 1)])
    m = gran_m.resolver(p)
    assert m["estado"] == "optimo" and m["z"] == F(-5, 4) and len(m["tablas"]) < 100


def test_paso_a_paso_del_caso_real_coincide_con_el_informe():
    """Variables que entran/salen, pivotes y z de cada tabla (informe, sección Gran M)."""
    m = gran_m.resolver(caso_real())
    t = m["tablas"]
    assert len(t) == 5 and [(x["entra"], x["sale"]) for x in t[:4]] == [("x2", "s4"), ("x1", "A1"), ("s1", "A2"), ("s4", "s1")]
    assert [round(float(x["pivote"]), 4) for x in t[:4]] == [0.748, 0.0537, 7.1174, 0.37]
    assert t[0]["base"] == ["A1", "A2", "s3", "s4"] and t[0]["z"].m == F("8.347") and t[0]["z"].k == 0
    assert round(float(t[1]["z"].m), 4) == 8.347                          # la iteración 1 es degenerada: z no cambia
    assert round(float(t[2]["z"].k), 2) == 12748.32 and round(float(t[2]["z"].m), 4) == 1.4715
    assert round(float(t[3]["z"].k), 2) == 15860.14 and t[3]["z"].m == 0
    assert [c.texto(4) for c in t[0]["cz"][:4]] == ["600 - 0,3526M", "3200 - 1,2804M", "M", "M"]
    final = dict(zip(t[4]["base"], t[4]["b"]))
    assert final["s3"] == 1 and round(float(final["s4"]), 4) == 0.5588 and round(float(m["z"]), 2) == 14859.80


def test_propiedades_metamorficas():
    """Cambios que no deben alterar la respuesta (o que la alteran de forma conocida)."""
    rng = random.Random(77)
    n_ok = 0
    for _ in range(250):
        p = aleatorio(rng, rng.choice([2, 3, 4]), rng.randint(1, 4))
        m = gran_m.resolver(p)
        if m["estado"] != "optimo":
            continue
        n_ok += 1
        q = replace(p, tipo="min" if p.tipo == "max" else "max", c=tuple(-v for v in p.c))        # max c = -min(-c)
        assert gran_m.resolver(q)["z"] == -m["z"]
        perm = list(p.restr); rng.shuffle(perm)                                                    # orden de restricciones
        assert gran_m.resolver(replace(p, restr=tuple(perm)))["z"] == m["z"]
        i = rng.randrange(len(p.restr)); r = p.restr[i]                                            # escalar una restricción
        rs = list(p.restr); rs[i] = replace(r, a=tuple(3 * v for v in r.a), b=3 * r.b)
        p3 = replace(p, restr=tuple(rs)); m3 = gran_m.resolver(p3)
        assert m3["z"] == m["z"]
        s0, s3 = sensibilidad.analizar(p, m["estandar"]), sensibilidad.analizar(p3, m3["estandar"])
        if s0 and s3:
            assert s3["precios"][i]["precio"] == s0["precios"][i]["precio"] / 3                   # el precio sombra se divide
        assert gran_m.resolver(replace(p, c=tuple(5 * v for v in p.c)))["z"] == 5 * m["z"]        # escalar el objetivo
        if len(p.restr) >= 2 and all(x.signo == "<=" for x in p.restr[:2]):                       # restricción redundante
            a = tuple(x + y for x, y in zip(p.restr[0].a, p.restr[1].a))
            extra = Restriccion("red", "", a, "<=", p.restr[0].b + p.restr[1].b)
            assert gran_m.resolver(replace(p, restr=p.restr + (extra,)))["z"] == m["z"]
    assert n_ok > 50


def test_sensibilidad_con_artificial_en_nivel_cero():
    """La base final conserva una artificial en 0; el motor la saca y la sensibilidad sigue siendo exacta."""
    p = P("min", [-1, -5], [([3, 2], "=", 18), ([1, 2], "<=", 6)])
    m = gran_m.resolver(p)
    assert m["estado"] == "optimo" and m["x"] == [6, 0] and m["z"] == -6
    assert any(j >= len(m["estandar"]["c"]) for j in m["estandar"]["base"])      # sí hay artificial en la base
    s = sensibilidad.analizar(p, m["estandar"])
    assert s is not None
    for i, f in enumerate(s["precios"]):
        for nb in [x for x in (f["lo"], f["hi"]) if x is not None]:
            n2 = gran_m.resolver(con_b(p, i, nb))
            assert n2["estado"] == "optimo" and n2["z"] == m["z"] + f["precio"] * (nb - f["b"])
    for j, f in enumerate(s["cj"]):
        for nc in [x for x in (f["lo"], f["hi"]) if x is not None]:
            nuevo = [v if k != j else nc for k, v in enumerate(p.c)]
            assert gran_m.resolver(con_c(p, j, nc))["z"] == sum(c * x for c, x in zip(nuevo, m["x"]))


def test_sensibilidad_reparada_en_aleatorios():
    rng = random.Random(321)
    reparados = 0
    for _ in range(1500):
        p = aleatorio(rng, rng.choice([2, 3, 4]), rng.randint(2, 5))
        m = gran_m.resolver(p)
        if m["estado"] != "optimo" or not any(j >= len(m["estandar"]["c"]) for j in m["estandar"]["base"]):
            continue
        s = sensibilidad.analizar(p, m["estandar"])
        if s is None:
            continue
        reparados += 1
        for i, f in enumerate(s["precios"]):
            for nb in [x for x in (f["lo"], f["hi"]) if x is not None]:
                assert gran_m.resolver(con_b(p, i, nb))["z"] == m["z"] + f["precio"] * (nb - f["b"])
    assert reparados >= 3


def test_restriccion_redundante_da_mensaje_y_no_error():
    """Dos igualdades que dicen lo mismo: no hay base completa; la web lo explica en vez de ocultarlo."""
    from app import app
    d = completar({"n": 2, "m": 2, "tipo": "min", "metodo": "gran_m", "nombre_z": "z", "unidad_z": "",
                   "vars": [{"nombre": "x1", "unidad": "", "c": "1"}, {"nombre": "x2", "unidad": "", "c": "1"}],
                   "restr": [{"nombre": "A", "unidad": "", "a": ["1", "1"], "signo": "=", "b": "4"},
                             {"nombre": "B", "unidad": "", "a": ["2", "2"], "signo": "=", "b": "8"}]})
    r = app.test_client().post("/resolver", data=forma(d, "gran_m"))
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "restricción redundante" in html and "4,00" in html


def test_nombres_con_dolar_no_rompen_la_grafica():
    """matplotlib lee $...$ como fórmula; los nombres escritos por el usuario no deben causar un error 500."""
    from app import app
    with open(os.path.join(EJ, "prueba1_alternativos.json"), encoding="utf-8") as fh:
        d = completar(json.load(fh))
    for nombre in ["Costo $ por día", "$x^$", "Precio $5 y $10", "100% $ ahorro", "a_b^c", "\\frac{"]:
        d["restr"][0]["nombre"] = d["vars"][0]["nombre"] = d["vars"][0]["unidad"] = d["nombre_z"] = nombre
        r = app.test_client().post("/resolver", data=forma(d, "grafico"))
        assert r.status_code == 200 and "data:image/png" in r.get_data(as_text=True), nombre


def test_la_web_resiste_entradas_basura():
    from app import app
    c, rng = app.test_client(), random.Random(3)
    with open(os.path.join(EJ, "dieta.json"), encoding="utf-8") as fh:
        d = completar(json.load(fh))
    basura = ["", "  ", "abc", "1e999999", "0,0,0", "1/0", "<script>alert(1)</script>", "nan", "inf", "1" * 500, "💥",
              "- 3", "4 5", "$x^$", "\x00"]
    for _ in range(150):
        f = forma(d, rng.choice(["grafico", "gran_m", "otro", ""]))
        for k in list(f):
            if rng.random() < 0.12:
                f[k] = rng.choice(basura)
        if rng.random() < 0.15:
            f["n"] = rng.choice(["0", "-1", "99", "x", "", "3"])
        if rng.random() < 0.15:
            f["m"] = rng.choice(["0", "-1", "99", "x", "", "8"])
        if rng.random() < 0.1:
            f.pop(rng.choice(list(f)), None)
        r = c.post("/resolver", data=f)
        html = r.get_data(as_text=True)
        assert r.status_code == 200 and "Traceback" not in html and "<script>alert(1)</script>" not in html
    for nn in ["", "x", "-5", "999", "3"]:
        for mm in ["", "x", "0", "9", "2"]:
            f = forma(d, "gran_m"); f["nuevo_n"], f["nuevo_m"] = nn, mm
            assert c.post("/redimensionar", data=f).status_code == 200


def test_alternativos_sin_falsos_positivos_ni_negativos():
    """El aviso de óptimos alternativos se compara con un oráculo: ¿la cara óptima es más que un punto?"""
    if linprog is None:
        return
    rng = random.Random(8)
    revisados = 0
    for _ in range(300):
        p = aleatorio(rng, 2, rng.randint(1, 4))
        if rng.random() < 0.5:
            p = replace(p, c=tuple(F(rng.choice([0, 1, 2, -1, -2])) for _ in range(2)))
        if not any(p.c):
            continue
        m = gran_m.resolver(p)
        if m["estado"] != "optimo":
            continue
        Aub, bub, Aeq, beq = [], [], [[float(v) for v in p.c]], [float(m["z"])]
        for r in p.restr:
            a = [float(v) for v in r.a]
            if r.signo == "=":
                Aeq.append(a); beq.append(float(r.b))
            elif r.signo == "<=":
                Aub.append(a); bub.append(float(r.b))
            else:
                Aub.append([-v for v in a]); bub.append(-float(r.b))
        ancho = 0.0
        for j in range(2):
            lim = []
            for sg in (1, -1):
                cc = [0.0, 0.0]; cc[j] = sg
                res = linprog(cc, A_ub=Aub or None, b_ub=bub or None, A_eq=Aeq, b_eq=beq, bounds=(0, None), method="highs")
                lim.append(res.fun if res.status == 0 else float("inf"))
            ancho = max(ancho, -lim[1] - lim[0])
        es_punto = ancho < 1e-7
        for res in (m, grafico.resolver(p)):
            assert any("alternativos" in t for _, t in res["avisos"]) == (not es_punto), p
        revisados += 1
    assert revisados > 100


def test_degeneracion_a_mitad_del_camino():
    """La razón mínima es 0 en la primera iteración, aunque el óptimo final no tenga variables básicas en 0."""
    p = P("min", [-3, -4], [([4, 4], "<=", 17), ([-3, 4], "<=", 0)])
    m = gran_m.resolver(p)
    assert m["estado"] == "optimo" and all(b != 0 for b in m["tablas"][-1]["b"])
    assert any("Degeneración" in t for _, t in m["avisos"])
