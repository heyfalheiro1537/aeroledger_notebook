"""Dados do SBSJ usados nos experimentos, cada um com a fonte.

Premissas entram no ledger e nunca são usadas para validar a si mesmas; os
valores publicados que servem de comparação ficam nas verificações do notebook.

Fontes:
  AD 2.12 e AD 2.13 — AIP Brasil, eAIP edição 20-2026 (01 OCT 2026)
  ADC — Carta de Aeródromo SBSJ, AIRAC AMDT 2604A1 (16 APR 26)
  AOC — Carta de Obstáculos Tipo A SBSJ, AIRAC AMDT 2213A1 (29 DEC 22)
"""
from datetime import datetime, timezone

UTC = timezone.utc

# ---------------------------------------------------------------- datas das edições
AIRAC_2213 = datetime(2022, 12, 29, tzinfo=UTC)     # AOC
AIRAC_2604 = datetime(2026, 4, 16, tzinfo=UTC)      # ADC
EAIP_20_2026 = datetime(2026, 10, 1, tzinfo=UTC)    # AD 2.12 e AD 2.13

# ---------------------------------------------------------------- premissas (AD 2.12)
THR16 = {"lat": "231310.79S", "lon": "0455219.08W", "elev_m": 619.3, "gund_m": -2.6}
THR34 = {"lat": "231412.21S", "lon": "0455112.46W", "elev_m": 647.0, "gund_m": -3.0}
LARGURA_RWY = 45
SWY = {"comprimento": 283, "largura": 45}             # além da THR 34; dá ASDA à RWY 16
SUPERFICIE = "ASPH"

# ---------------------------------------------------------------- premissas das direções (AD 2.13)
# A regra das distâncias declaradas não lê ausência como zero: cada direção afirma o
# deslocamento da cabeceira e se há SWY e CWY. A AD 2.13 publica LDA = TORA nas duas
# direções (sem deslocamento), TODA = TORA (sem CWY) e ASDA 16 > TORA 16 (a SWY além da
# THR 34). A observação da AD 2.12 para a RWY 34 fala em "THR 34 deslocada", o que a
# tabela não reflete; o cenário adota a tabela e registra o conflito no motivo.
# Como estes valores são lidos das distâncias publicadas, a comparação de TODA e LDA no
# E2 não é independente deles: ela confere a regra, não o deslocamento nem a CWY.
DIRECOES = {
    "16": {"deslocamento_m": 0, "tem_swy": True, "tem_cwy": False},
    "34": {"deslocamento_m": 0, "tem_swy": False, "tem_cwy": False},
}
MOTIVO_DIRECOES = {
    "16": "eAIP 20-2026, AD 2.12 (posição); AD 2.13: LDA 16 = TORA 16 e TODA 16 = TORA 16; ASDA 16 inclui a SWY",
    "34": "eAIP 20-2026, AD 2.12 (posição); AD 2.13: LDA 34 = TORA 34, sem SWY nem CWY. "
          "A observação da AD 2.12 descreve a THR 34 como deslocada, o que a AD 2.13 não reflete; adotada a AD 2.13",
}

# ---------------------------------------------------------------- norma (ADC)
VARIACAO_LESTE = -22.0                                 # VAR 22°W 2026 (oeste negativo)

# ---------------------------------------------------------------- E1: as duas edições em "modo forma"
FORMA_AIRAC_2213 = {                                   # AOC
    "pista": {"comprimento": 2676, "largura": 45},
    "swy": {"comprimento": 325, "largura": 45},
    "faixa": {"comprimento": 3121, "largura": 300},
    "distancias": {"rwy16": {"tora": 2676, "toda": 2676, "asda": 3001, "lda": 2676},
                   "rwy34": {"tora": 2676, "toda": 2676, "asda": 2676, "lda": 2676}},
}
FORMA_AIRAC_2604 = {                                   # ADC
    "pista": {"comprimento": 2675, "largura": 45},
    "swy": {"comprimento": 283, "largura": 45},
    "faixa": {"comprimento": 3118, "largura": 280},
    "distancias": {"rwy16": {"tora": 2675, "toda": 2675, "asda": 2958, "lda": 2675},
                   "rwy34": {"tora": 2675, "toda": 2675, "asda": 2675, "lda": 2675}},
}

# ---------------------------------------------------------------- E2: remedição simulada da THR 34
# 1,00 m para fora no prolongamento do eixo e 0,50 m para sudoeste, republicada
# a 0,01" como o AIP publicaria (deslocamento efetivo: 0,966 m).
THR34_REMEDIDA = {"lat": "231412.24S", "lon": "0455112.45W", "elev_m": 647.0, "gund_m": -3.0}

# cantos da pista e da SWY conferidos contra o gabarito: (referente, s, o)
VERTICES = [("THR16", 0, 22.5), ("THR16", 0, -22.5), ("THR34", 0, 22.5), ("THR34", 0, -22.5),
            ("THR34", -283, 22.5), ("THR34", -283, -22.5)]


def gms(texto):
    """'231310.79S' → graus decimais (sul e oeste negativos)."""
    h = texto[-1]
    corpo = texto[:-1]
    inteiro, _, frac = corpo.partition(".")
    gw = 2 if h in "NS" else 3
    g, m = int(inteiro[:gw]), int(inteiro[gw:gw + 2])
    s = float(inteiro[gw + 2:] + ("." + frac if frac else ""))
    v = g + m / 60 + s / 3600
    return -v if h in "SW" else v
