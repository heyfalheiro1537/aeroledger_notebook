"""Funções pequenas que o notebook usa para não repetir código nas células."""
import json
import os
from datetime import timedelta
from pathlib import Path

import psycopg

import aeroledger as al
import fontes as F

ADMIN = os.environ.get("AEROLEDGER_DSN_ADMIN", "postgresql://aeroledger@localhost:54329/postgres")
BASE = ADMIN.rsplit("/", 1)[0]
BANCO = "aeroledger_experimentos"
ELEMENTO = "RWY_16_34"


# ---------------------------------------------------------------- banco

def banco_novo(nome=BANCO):
    """Recria o banco dos experimentos, vazio, com o esquema da biblioteca."""
    with psycopg.connect(ADMIN, autocommit=True) as a:
        a.execute(f"DROP DATABASE IF EXISTS {nome} WITH (FORCE)")
        a.execute(f"CREATE DATABASE {nome}")
    conn = psycopg.connect(f"{BASE}/{nome}")
    al.criar_esquema(conn)
    return conn


def reconectar(nome=BANCO):
    return psycopg.connect(f"{BASE}/{nome}")


def copia(origem, destino):
    """Cópia do banco 'origem' (o PostgreSQL exige que ela não tenha conexões abertas)."""
    with psycopg.connect(ADMIN, autocommit=True) as a:
        a.execute(f"DROP DATABASE IF EXISTS {destino}")
        a.execute(f"CREATE DATABASE {destino} TEMPLATE {origem}")
    return psycopg.connect(f"{BASE}/{destino}")


def apagar(nome):
    with psycopg.connect(ADMIN, autocommit=True) as a:
        a.execute(f"DROP DATABASE IF EXISTS {nome}")


def contar(conn, sql, *params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def ultimo_event_id(conn, run):
    return contar(conn, "SELECT coalesce(max(event_id), 0) FROM event WHERE run_id = %s", run)


def escritos_depois_de(conn, run, marco):
    """[(event_id, feature_id, feature_type, event_type, [campos])] escritos depois de 'marco'."""
    with conn.cursor() as cur:
        cur.execute("""SELECT e.event_id, e.feature_id, e.feature_type, e.event_type,
                              array_remove(array_agg(f.path ORDER BY f.path), NULL)
                       FROM event e LEFT JOIN event_field f USING (event_id)
                       WHERE e.run_id = %s AND e.event_id > %s GROUP BY 1, 2, 3, 4 ORDER BY 1""", (run, marco))
        return cur.fetchall()


# ---------------------------------------------------------------- tempo

def avancar_ate(conn, run, instante):
    return al.avancar(conn, run, segundos=(instante - al.agora(conn, run)).total_seconds())


def um_segundo_antes(t):
    return t - timedelta(seconds=1)


# ---------------------------------------------------------------- SBSJ no modelo

def _referente(p, fonte):
    return {"lat": F.gms(p["lat"]), "lon": F.gms(p["lon"]), "elev_m": p["elev_m"], "gund_m": p["gund_m"],
            "fonte": fonte}


def referencial(thr34=None, fonte34="eAIP 20-2026, AD 2.12"):
    """Corpo do referencial: as duas cabeceiras e o eixo da pista entre elas."""
    return {
        "datum": "SIRGAS2000",
        "origem_local": "THR16",
        "referentes": {
            "THR16": _referente(F.THR16, "eAIP 20-2026, AD 2.12"),
            "THR34": _referente(thr34 or F.THR34, fonte34),
        },
        "elementos_lineares": {ELEMENTO: ["THR16", "THR34"]},
    }


def seed(ref, s=0.0, o=0.0):
    """Posição relativa a um referente: s ao longo do eixo, o para a direita."""
    return {"elemento": ELEMENTO, "referente": ref, "s": float(s), "o": float(o)}


def latlon(corpo, nome):
    r = corpo["referentes"][nome]
    return r["lat"], r["lon"]


# ---------------------------------------------------------------- exportação (E5)

def exportar(conn, run, caminho):
    """O run como um terceiro o receberia: eventos (envelope, campos, hash) e referenciais, em JSON.

    Usa SQL direto, sem a biblioteca: o arquivo é só o que está no banco.
    """
    with conn.cursor() as cur:
        cur.execute("""SELECT event_id, run_id, feature_id, feature_type, event_type, asserted_by, owner_ref,
                              reason, caused_by, prev_hash, grupo_id, grupo_n, hash
                       FROM event WHERE run_id = %s ORDER BY event_id""", (run,))
        nomes = [d.name for d in cur.description]
        eventos = [dict(zip(nomes, r)) for r in cur.fetchall()]
        cur.execute("SELECT event_id, path, op, next FROM event_field WHERE run_id = %s", (run,))
        campos = {}
        for eid, path, op, nxt in cur.fetchall():
            campos.setdefault(eid, []).append({"path": path, "op": op, "next": nxt})
        cur.execute("SELECT ref_id, corpo FROM referencial")
        refs = {rid: corpo for rid, corpo in cur.fetchall()}
    for e in eventos:
        e["campos"] = campos.get(e["event_id"], [])
    Path(caminho).write_text(json.dumps({"run_id": run, "eventos": eventos, "referenciais": refs},
                                        ensure_ascii=False, indent=1))
    return caminho
