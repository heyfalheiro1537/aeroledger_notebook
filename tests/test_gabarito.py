"""O gabarito geodésico contra o caso publicado de Vincenty no GRS80 (Geoscience Australia):
Flinders Peak → Buninyong, 54 972,271 m; azimutes 306°52'05,37" e 127°10'25,07"."""
from geodesia import aip, direta, dms, inversa

FP = (dms(37, 57, 3.72030, "S"), dms(144, 25, 29.52440, "E"))
BU = (dms(37, 39, 10.15610, "S"), dms(143, 55, 35.38390, "E"))
S, AZ12, AZ21 = 54972.271, dms(306, 52, 5.37, "N"), dms(127, 10, 25.07, "N")


def test_inversa():
    s, az12, az21 = inversa(*FP, *BU)
    assert abs(s - S) < 0.0005
    assert abs(az12 - AZ12) < 0.005 / 3600 and abs(az21 - AZ21) < 0.005 / 3600


def test_direta():
    lat, lon, _ = direta(*FP, AZ12, S)
    assert abs(lat - BU[0]) < 0.0001 / 3600 and abs(lon - BU[1]) < 0.0001 / 3600


def test_pontos_identicos():
    assert inversa(*FP, *FP) == (0.0, 0.0, 0.0)


def test_formato_aip():
    assert abs(aip("231310.79S") - dms(23, 13, 10.79, "S")) < 1e-12
