"""Ataques do E4: o atacante escreve direto no PostgreSQL, sem a biblioteca.

Cada ataque roda numa cópia do banco; o original nunca é tocado.

k é um evento do meio da cadeia: o primeiro, a partir da metade, que tem campos
no corpo, não é causa de outro evento e tem espaço livre de event_id logo
depois (para caber o evento inserido).
"""
from psycopg.types.json import Jsonb

from aeroledger import ledger
from aeroledger.canonico import sha256
from aeroledger.ledger import ENVELOPE, conteudo_para_hash

ATAQUES = {
    "alterar": "alterar o corpo do evento k sem recalcular o hash",
    "apagar": "apagar o evento k",
    "inserir": "inserir um evento entre k e o seguinte, com hash próprio correto",
    "reescrever": "alterar k e recalcular todos os hashes de k até o fim",
}


def _eventos(cur, run_id):
    cur.execute("SELECT event_id FROM event WHERE run_id = %s ORDER BY event_id", (run_id,))
    return [r[0] for r in cur.fetchall()]


def escolher_k(conn, run_id):
    """(k, evento seguinte a k, último evento)."""
    with conn.cursor() as cur:
        ids = _eventos(cur, run_id)
        cur.execute("SELECT DISTINCT caused_by FROM event WHERE caused_by IS NOT NULL")
        causas = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT DISTINCT event_id FROM event_field WHERE run_id = %s", (run_id,))
        com_campos = {r[0] for r in cur.fetchall()}
    for i in range(len(ids) // 2, len(ids) - 1):
        k = ids[i]
        if k in com_campos and k not in causas and ids[i + 1] - k > 1:
            return k, ids[i + 1], ids[-1]
    raise RuntimeError("nenhum evento serve como k")


def _rehash(cur, eid):
    cur.execute(f"SELECT {', '.join(ENVELOPE)} FROM event WHERE event_id = %s", (eid,))
    env = dict(zip(ENVELOPE, cur.fetchone()))
    cur.execute("SELECT path, op, next FROM event_field WHERE event_id = %s", (eid,))
    campos = [{"path": p, "op": o, "next": n} for p, o, n in cur.fetchall()]
    h = sha256(conteudo_para_hash(env, campos))
    cur.execute("UPDATE event SET hash = %s WHERE event_id = %s", (h, eid))
    return h


def _mexer_no_corpo(cur, eid):
    cur.execute("SELECT path FROM event_field WHERE event_id = %s ORDER BY path LIMIT 1", (eid,))
    path = cur.fetchone()[0]
    cur.execute("UPDATE event_field SET next = %s, op = 'set' WHERE event_id = %s AND path = %s",
                (Jsonb("adulterado"), eid, path))


def atacar(conn, run_id, ataque, k):
    with conn.cursor() as cur:
        if ataque == "alterar":
            _mexer_no_corpo(cur, k)
        elif ataque == "apagar":
            cur.execute("DELETE FROM event_field WHERE event_id = %s", (k,))
            cur.execute("DELETE FROM event WHERE event_id = %s", (k,))
        elif ataque == "inserir":
            cur.execute("SELECT hash FROM event WHERE event_id = %s", (k,))
            prev = cur.fetchone()[0]
            novo = k + 1
            env = {"event_id": novo, "run_id": run_id, "feature_id": "SBSJ-FALSO", "feature_type": "incident",
                   "event_type": "BASELINE", "asserted_by": "intruso", "owner_ref": None, "reason": None,
                   "caused_by": None, "prev_hash": prev}
            campos = [{"path": "texto", "op": "set", "next": "evento inserido"}]
            h = sha256(conteudo_para_hash(env, campos))
            cur.execute("""INSERT INTO event (event_id, run_id, feature_id, feature_type, event_type, asserted_by,
                           owner_ref, reason, caused_by, prev_hash, hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (novo, run_id, "SBSJ-FALSO", "incident", "BASELINE", "intruso", None, None, None, prev, h))
            cur.execute("INSERT INTO event_field VALUES (%s,%s,%s,%s,%s,%s)",
                        (novo, run_id, "SBSJ-FALSO", "texto", "set", Jsonb("evento inserido")))
        elif ataque == "reescrever":
            _mexer_no_corpo(cur, k)
            ids = [i for i in _eventos(cur, run_id) if i >= k]
            cur.execute("SELECT hash FROM event WHERE run_id = %s AND event_id < %s ORDER BY event_id DESC LIMIT 1",
                        (run_id, k))
            ant = cur.fetchone()[0]
            for i in ids:
                cur.execute("UPDATE event SET prev_hash = %s WHERE event_id = %s", (ant, i))
                ant = _rehash(cur, i)
        else:
            raise ValueError(ataque)
    conn.commit()


def detectar(conn, run_id, ancora):
    """(o que verificar_cadeia devolve, se a comparação com a âncora detecta)."""
    vc = ledger.verify_chain(conn, run_id)
    cab = ledger.cabeca(conn, run_id)
    return vc, bool(vc) or tuple(cab) != tuple(ancora)


# ---------------------------------------------------------------- E6: ataques ao tópico
# O atacante agora está no canal (o broker), não no banco. O ledger nunca é tocado.

ATAQUES_TOPICO = {
    "alterar": "trocar o referencial adotado na mensagem k, sem recalcular o hash",
    "alterar_rehash": "trocar o referencial na mensagem k e recalcular o hash dela",
    "remover": "remover a mensagem k",
    "inserir": "inserir um evento falso depois de k, com elo e hash corretos",
    "truncar_fim": "remover as últimas mensagens",
    "anexar_fim": "anexar no fim um evento falso, com elo e hash corretos",
}


def _falso(depois_de, run_id):
    from aeroledger.topico import hash_do_evento
    ev = {"event_id": depois_de["event_id"] + 1, "run_id": run_id, "feature_id": "SBSJ-FALSO",
          "feature_type": "restriction", "event_type": "BASELINE", "asserted_by": "intruso",
          "owner_ref": "SBSJ-RWY", "reason": None, "caused_by": None, "prev_hash": depois_de["hash"],
          "grupo_id": None, "grupo_n": None,
          "campos": [{"path": "adc.texto", "op": "set", "next": "RWY 16/34 fechada"}]}
    ev["hash"] = hash_do_evento(ev)
    return {"tipo": "evento", "evento": ev}


def atacar_topico(topico, ataque, k_event_id, campo, valor_falso):
    """Adultera as mensagens do tópico (em memória) e devolve o índice da mensagem k."""
    from aeroledger.topico import hash_do_evento
    msgs = topico.mensagens
    i = next(i for i, m in enumerate(msgs) if m["tipo"] == "evento" and m["evento"]["event_id"] == k_event_id)
    ev = msgs[i]["evento"]
    if ataque in ("alterar", "alterar_rehash"):
        for c in ev["campos"]:
            if c["path"] == campo:
                c["next"] = valor_falso
        if ataque == "alterar_rehash":
            ev["hash"] = hash_do_evento(ev)
    elif ataque == "remover":
        del msgs[i]
    elif ataque == "inserir":
        msgs.insert(i + 1, _falso(ev, ev["run_id"]))
    elif ataque == "truncar_fim":
        del msgs[-2:]
    elif ataque == "anexar_fim":
        ultimo = next(m["evento"] for m in reversed(msgs) if m["tipo"] == "evento")
        msgs.append(_falso(ultimo, ultimo["run_id"]))
    else:
        raise ValueError(ataque)
    return i
