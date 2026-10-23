"""Representación del problema de PL y formato de números (fracciones exactas)."""
from dataclasses import dataclass
from fractions import Fraction
from functools import total_ordering

SIGNOS = ("<=", ">=", "=")
INVERSO = {"<=": ">=", ">=": "<=", "=": "="}


@dataclass(frozen=True)
class Restriccion:
    nombre: str
    unidad: str
    a: tuple      # coeficientes de cada variable (Fraction)
    signo: str    # "<=", ">=" o "="
    b: Fraction   # lado derecho


@dataclass(frozen=True)
class Problema:
    tipo: str         # "max" o "min"
    nombre_z: str
    unidad_z: str
    nombres: tuple    # nombre de cada variable
    unidades: tuple   # unidad de cada variable
    c: tuple          # coeficientes de la función objetivo (Fraction)
    restr: tuple      # tuple[Restriccion]


@total_ordering
class MNum:
    """Número a + b·M (M simbólica, 'muy grande'). Se compara primero por b y luego por a."""
    __slots__ = ("k", "m")

    def __init__(self, k=0, m=0):
        self.k, self.m = Fraction(k), Fraction(m)

    def __add__(self, o): return MNum(self.k + o.k, self.m + o.m)
    def __sub__(self, o): return MNum(self.k - o.k, self.m - o.m)
    def __mul__(self, f): return MNum(self.k * f, self.m * f)
    def _key(self): return (self.m, self.k)
    def __eq__(self, o): return self._key() == o._key()
    def __lt__(self, o): return self._key() < o._key()
    __hash__ = None

    def texto(self, d=4):
        if self.m == 0:
            return fmt(self.k, d)
        m = "M" if abs(self.m) == 1 else fmt(abs(self.m), d) + "M"
        if self.k == 0:
            return ("-" if self.m < 0 else "") + m
        return f"{fmt(self.k, d)} {'-' if self.m < 0 else '+'} {m}"


def a_fraccion(texto):
    """Convierte texto a Fraction ('0,5', '1/3', '-2'). Lanza ValueError si no es número."""
    t = str(texto).strip().replace(",", ".")
    if not t or len(t) > 24 or "_" in t or "e" in t.lower():
        raise ValueError(texto)
    try:
        v = Fraction(t)
    except ZeroDivisionError:
        raise ValueError(texto)
    if abs(v) > 10**12:
        raise ValueError(texto)
    return v


def fmt(x, d=4):
    """Formato con coma decimal; enteros sin decimales; quita ceros finales."""
    if isinstance(x, MNum):
        return x.texto(d)
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    s = f"{float(x):.{d}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s.replace(".", ",")


def moneda(x):
    """14859.8 -> '14.859,80'."""
    s = f"{float(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
