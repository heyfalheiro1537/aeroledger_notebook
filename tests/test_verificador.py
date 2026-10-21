"""A forma canônica do verificador independente (escrita pelo RFC 8785) e a da biblioteca dão o mesmo texto.

Foi esta comparação que achou um erro na biblioteca: floats inteiros acima de 2^53
saíam com os dígitos binários exatos em vez dos dígitos mais curtos (corrigido).
"""
import random

from aeroledger.canonico import canonico

from verificador_independente import jcs


def test_numeros():
    r = random.Random(1)
    casos = [0.0, 1.0, 0.5, 619.3, -2.6, 1e21, 1e20, 1e-7, 1e-6, 5e-324, 1.7976931348623157e308,
             5.1521516039062726e+17, 2.0 ** 53]
    casos += [r.uniform(-1e3, 1e3) for _ in range(20000)]
    casos += [(-1) ** r.randint(0, 1) * 10 ** r.uniform(-30, 30) for _ in range(20000)]
    casos += [float(r.randint(0, 10 ** 22)) for _ in range(5000)]
    for x in casos:
        assert jcs(x).encode() == canonico(x), x


def test_objetos():
    v = {"b": [1, 2.5, None, True], "a": {"€": "x", "\r": 0.0}, "1": "ç"}
    assert jcs(v).encode() == canonico(v)
