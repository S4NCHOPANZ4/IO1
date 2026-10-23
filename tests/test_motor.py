"""Pruebas automáticas del motor (pytest). Ejecutar: pytest"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from motor import grafico, gran_m
from motor.validacion import completar, parsear

EJ = os.path.join(os.path.dirname(__file__), "..", "ejemplos")


def cargar(nombre):
    with open(os.path.join(EJ, nombre + ".json"), encoding="utf-8") as f:
        p, err = parsear(completar(json.load(f)))
    assert not err, err
    return p


def test_vertices_del_caso_real():
    r = grafico.resolver(cargar("dieta"))
    pts = sorted((round(float(v["x"]), 2), round(float(v["y"]), 2)) for v in r["vertices"])
    assert pts == [(19.62, 1.28), (21.33, 0.64), (22.23, 1.45), (25.12, 0.38)]


def test_optimo_del_caso_real():
    r = grafico.resolver(cargar("dieta"))
    assert r["estado"] == "optimo" and abs(float(r["z"]) - 14859.80) < 0.01


def test_optimos_alternativos():
    r = grafico.resolver(cargar("prueba1_alternativos"))
    assert r["z"] == 16 and len(r["optimos"]) == 2
    assert any("alternativos" in t for _, t in r["avisos"])


def test_infactible():
    p = cargar("prueba2_infactible")
    assert grafico.resolver(p)["estado"] == "infactible" and gran_m.resolver(p)["estado"] == "infactible"


def test_no_acotado():
    p = cargar("prueba3_no_acotado")
    assert grafico.resolver(p)["estado"] == "no_acotado" and gran_m.resolver(p)["estado"] == "no_acotado"


def test_gran_m_coincide_con_grafico():
    p = cargar("dieta")
    g, m = grafico.resolver(p), gran_m.resolver(p)
    assert m["estado"] == "optimo" and m["z"] == g["z"]
    assert (m["x"][0], m["x"][1]) == (g["optimos"][0]["x"], g["optimos"][0]["y"])


def test_rechaza_datos_invalidos():
    with open(os.path.join(EJ, "dieta.json"), encoding="utf-8") as f:
        d = completar(json.load(f))
    d["restr"][0]["b"] = ""            # campo vacío
    d["vars"][0]["c"] = "abc"          # texto en vez de número
    d["restr"][1]["a"] = ["0", "0"]    # dato imposible
    p, err = parsear(d)
    assert p is None and len(err) == 3
