"""Aplicación Flask: recibe el formulario, llama al motor y devuelve la página.
Esta capa no hace cálculos de programación lineal."""
import json
import os

from flask import Flask, abort, render_template, request

from motor import grafico, gran_m, sensibilidad
from motor.modelo import fmt, moneda
from motor.validacion import (MAX_N, completar, datos_desde_form, datos_vacios, parsear, redimensionar)

app = Flask(__name__)
app.jinja_env.filters["fmt"] = fmt
app.jinja_env.filters["moneda"] = moneda
EJEMPLOS = os.path.join(os.path.dirname(__file__), "ejemplos")


def lista_ejemplos():
    out = []
    for f in sorted(os.listdir(EJEMPLOS)):
        if f.endswith(".json"):
            with open(os.path.join(EJEMPLOS, f), encoding="utf-8") as fh:
                out.append((f[:-5], json.load(fh)["titulo"]))
    return out


@app.context_processor
def contexto():
    return {"ejemplos": lista_ejemplos(), "max_n": MAX_N}


def pantalla_datos(d, errores=None, titulo=None):
    return render_template("datos.html", d=d, errores=errores or [], titulo=titulo)


@app.get("/")
def inicio():
    """Pantalla de datos vacía."""
    return pantalla_datos(datos_vacios())


@app.get("/ejemplo/<nombre>")
def ejemplo(nombre):
    """Carga un ejemplo desde un archivo JSON en la tabla de coeficientes."""
    if nombre not in dict(lista_ejemplos()):
        abort(404)
    with open(os.path.join(EJEMPLOS, nombre + ".json"), encoding="utf-8") as fh:
        crudo = json.load(fh)
    return pantalla_datos(completar(crudo), titulo=crudo["titulo"])


@app.post("/redimensionar")
def cambiar_tamano():
    """Cambia el número de variables y restricciones conservando lo escrito."""
    d = datos_desde_form(request.form)
    n = max(1, min(MAX_N, int(request.form.get("nuevo_n", d["n"]) or d["n"]))) if request.form.get("nuevo_n", "").isdigit() else d["n"]
    m = max(1, min(MAX_N, int(request.form.get("nuevo_m", d["m"]) or d["m"]))) if request.form.get("nuevo_m", "").isdigit() else d["m"]
    return pantalla_datos(redimensionar(d, n, m), titulo=request.form.get("titulo"))


def texto_resultado(p, x, z):
    lineas = [f"{nom} = {fmt(v)}{' ' + u if u else ''}" for nom, u, v in zip(p.nombres, p.unidades, x)]
    return lineas, f"{p.nombre_z} = {moneda(z)}{' ' + p.unidad_z if p.unidad_z else ''}"


@app.post("/resolver")
def resolver():
    """Valida, resuelve con el método elegido y muestra el resultado."""
    d = datos_desde_form(request.form)
    p, errores = parsear(d)
    if errores:
        return pantalla_datos(d, errores, request.form.get("titulo"))
    titulo = request.form.get("titulo")
    gm = gran_m.resolver(p)
    sens, sens_msg = None, None
    if gm["estado"] == "optimo":
        sens = sensibilidad.analizar(p, gm["estandar"])
        if sens is None:
            sens_msg = ("No se pudo calcular el análisis de sensibilidad: hay una restricción redundante "
                        "(se deduce de las demás), así que la base óptima no queda completa.")

    if d["metodo"] == "grafico":
        res = grafico.resolver(p)
        imagen = grafico.dibujar(p, res)
        lineas = z = None
        if res["estado"] == "optimo":
            v = res["optimos"][0]
            lineas, z = texto_resultado(p, [v["x"], v["y"]], res["z"])
            if sens:
                grafico.comprobar_precios(p, res, sens)
        return render_template("resultado_grafico.html", p=p, res=res, imagen=imagen, lineas=lineas, z=z,
                               sens=sens, sens_msg=sens_msg, d=d, titulo=titulo)

    lineas = z = None
    if gm["estado"] == "optimo":
        lineas, z = texto_resultado(p, gm["x"], gm["z"])
    return render_template("resultado_granm.html", p=p, res=gm, lineas=lineas, z=z, sens=sens, sens_msg=sens_msg, d=d, titulo=titulo)


if __name__ == "__main__":
    app.run(debug=False)
