# Optimizador de PL · Grupo 5 (IO1-82)

App web en Flask que resuelve problemas de programación lineal con el método gráfico (2 variables) y la Gran M (hasta 8×8). Los dos métodos están programados desde cero; no usan SciPy ni otras librerías de optimización. También calcula precios sombra y rangos de sensibilidad.

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


## Carpetas

- `motor/`: los métodos y la sensibilidad
- `templates/` y `public/`: páginas y estilos
- `ejemplos/`: problemas en JSON
- `tests/`: pruebas automáticas
