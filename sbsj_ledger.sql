-- =====================================================================
-- Banco extraído do aeroledger (SQLite >= 3.45, JSONB nativo)
--
-- É o modelo de leitura distribuível: o mesmo registro que a biblioteca
-- grava no PostgreSQL, com o envelope em colunas e o corpo em JSONB.
-- Gerado por gerar_banco_sbsj.py a partir da biblioteca (aeroledger 0.6.0).
--
-- Convenções (as mesmas da biblioteca)
--   * Só se escreve: UPDATE e DELETE são bloqueados por gatilho.
--     Mudança é DELTA; fim do ciclo de vida de uma feature é VOID.
--   * event_id é um snowflake: ms desde 2000-01-01 UTC (41 bits) |
--     shard (10 bits) | sequência (12 bits). A ordem dos event_id é a
--     linha do tempo de transação; o instante sai do event_id (visão).
--   * corpo = as linhas do evento, ordenadas por path:
--       [{"path": "geometria.primitivos.pista.largura",
--         "op": "set" | "removed", "next": <valor JSON ou null>}, ...]
--     BASELINE traz todas as folhas da feature; DELTA só as que mudam;
--     VOID traz [].
--   * hash = SHA-256 da forma canônica (JCS, RFC 8785) de
--       {envelope sem hash (grupo_id/grupo_n só se presentes),
--        "campos": corpo}
--     O SQLite não calcula SHA-256: quem verifica refaz a forma canônica
--     a partir de json(corpo) e do envelope (ver gerar_banco_sbsj.py).
--   * Nada derivado é guardado: comprimento, azimute e distâncias
--     declaradas saem do referencial e das seeds, na leitura.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Procedência do arquivo
-- ---------------------------------------------------------------------
CREATE TABLE exportacao (
    chave  TEXT PRIMARY KEY,      -- biblioteca, commit, gerado_em, fontes, aviso
    valor  TEXT NOT NULL
);

CREATE TABLE run (
    run_id  TEXT PRIMARY KEY,     -- uma cadeia (ex.: sbsj, aixm)
    origem  TEXT NOT NULL         -- instante inicial declarado (ISO 8601 UTC)
);

-- ---------------------------------------------------------------------
-- Referenciais: endereçados pelo conteúdo, ref_id = sha256(JCS(corpo))
-- ---------------------------------------------------------------------
CREATE TABLE referencial (
    ref_id  TEXT PRIMARY KEY,
    corpo   BLOB NOT NULL CHECK (json_valid(corpo, 8))
);

-- ---------------------------------------------------------------------
-- Eventos: envelope em colunas, corpo em JSONB
-- ---------------------------------------------------------------------
CREATE TABLE evento (
    event_id      INTEGER PRIMARY KEY,
    run_id        TEXT    NOT NULL REFERENCES run(run_id),
    feature_id    TEXT    NOT NULL,
    feature_type  TEXT    NOT NULL,
    event_type    TEXT    NOT NULL CHECK (event_type IN ('BASELINE', 'DELTA', 'VOID')),
    asserted_by   TEXT    NOT NULL CHECK (length(asserted_by) > 0),
    owner_ref     TEXT,                                   -- feature dona
    reason        TEXT,                                   -- motivo declarado
    caused_by     INTEGER REFERENCES evento(event_id),    -- causa (evento → evento)
    prev_hash     TEXT,                                   -- NULL só no primeiro do run
    grupo_id      INTEGER,                                -- primeiro evento do grupo
    grupo_n       INTEGER,                                -- tamanho do grupo
    hash          TEXT    NOT NULL UNIQUE,
    corpo         BLOB    NOT NULL CHECK (json_valid(corpo, 8)),

    CHECK (json_type(corpo) = 'array'),
    CHECK (event_type <> 'VOID' OR (reason IS NOT NULL AND json_array_length(corpo) = 0)),
    CHECK (event_type =  'VOID' OR json_array_length(corpo) > 0),
    CHECK (caused_by IS NULL OR caused_by < event_id),
    CHECK ((grupo_id IS NULL) = (grupo_n IS NULL)),
    CHECK (grupo_id IS NULL OR (grupo_id <= event_id AND grupo_n >= 2)),
    UNIQUE (run_id, prev_hash)                            -- sem bifurcação da cadeia
);

CREATE INDEX evento_feature ON evento (run_id, feature_id, event_id);
CREATE INDEX evento_tipo    ON evento (run_id, feature_type, feature_id);
CREATE INDEX evento_owner   ON evento (owner_ref) WHERE owner_ref IS NOT NULL;
CREATE INDEX evento_causa   ON evento (caused_by) WHERE caused_by IS NOT NULL;

-- ---------------------------------------------------------------------
-- Só se escreve
-- ---------------------------------------------------------------------
CREATE TRIGGER evento_sem_update BEFORE UPDATE ON evento
BEGIN SELECT RAISE(ABORT, 'evento: só inserção; mude com DELTA, encerre com VOID'); END;

CREATE TRIGGER evento_sem_delete BEFORE DELETE ON evento
BEGIN SELECT RAISE(ABORT, 'evento: só inserção; encerre a feature com VOID'); END;

CREATE TRIGGER referencial_sem_update BEFORE UPDATE ON referencial
BEGIN SELECT RAISE(ABORT, 'referencial: imutável; publique um novo'); END;

CREATE TRIGGER referencial_sem_delete BEFORE DELETE ON referencial
BEGIN SELECT RAISE(ABORT, 'referencial: imutável'); END;

-- ordem e encadeamento: entra sempre no fim do run, ligado ao último hash
CREATE TRIGGER evento_encadeamento BEFORE INSERT ON evento
BEGIN
    SELECT RAISE(ABORT, 'evento: event_id anterior ao último do run')
    WHERE NEW.event_id <= (SELECT max(event_id) FROM evento WHERE run_id = NEW.run_id);
    SELECT RAISE(ABORT, 'evento: prev_hash não é o hash do último evento do run')
    WHERE NEW.prev_hash IS NOT (SELECT hash FROM evento WHERE run_id = NEW.run_id
                                ORDER BY event_id DESC LIMIT 1);
END;

-- forma das linhas do corpo
CREATE TRIGGER evento_linhas BEFORE INSERT ON evento
BEGIN
    SELECT RAISE(ABORT, 'evento: linha do corpo sem path, com op inválida ou removed com valor')
    WHERE EXISTS (
        SELECT 1 FROM json_each(NEW.corpo) l
        WHERE json_type(l.value, '$.path') IS NOT 'text'
           OR json_extract(l.value, '$.op') NOT IN ('set', 'removed')
           OR (json_extract(l.value, '$.op') = 'removed'
               AND json_type(l.value, '$.next') IS NOT 'null'));
END;

-- ---------------------------------------------------------------------
-- Visões de leitura (nada aqui é guardado)
-- ---------------------------------------------------------------------

-- envelope com o instante de transação e o corpo em texto
CREATE VIEW evento_legivel AS
SELECT event_id,
       strftime('%Y-%m-%dT%H:%M:%fZ', 946684800 + (event_id >> 22) / 1000.0, 'unixepoch') AS instante,
       run_id, feature_id, feature_type, event_type, asserted_by, owner_ref, reason,
       caused_by, grupo_id, grupo_n, prev_hash, hash, json(corpo) AS corpo
FROM evento;

-- uma linha por campo alterado (o corpo achatado)
CREATE VIEW campo AS
SELECT e.event_id, e.run_id, e.feature_id, e.event_type,
       json_extract(l.value, '$.path') AS path,
       json_extract(l.value, '$.op')   AS op,
       json_extract(l.value, '$.next') AS next,   -- escalar; objeto/lista como texto JSON
       json_type(l.value, '$.next')    AS tipo_next
FROM evento e, json_each(e.corpo) l;

-- cabeça de cada run: o hash a conferir contra a âncora externa
CREATE VIEW cabeca AS
SELECT run_id, event_id, hash FROM evento e
WHERE event_id = (SELECT max(event_id) FROM evento WHERE run_id = e.run_id);

-- estado atual: features vivas no último evento e seus campos
CREATE VIEW estado_atual AS
WITH ciclo AS (                       -- BASELINE vigente de cada feature
    SELECT run_id, feature_id, max(event_id) AS baseline
    FROM evento WHERE event_type = 'BASELINE'
    GROUP BY run_id, feature_id),
viva AS (                             -- sem VOID depois do BASELINE vigente
    SELECT c.* FROM ciclo c
    WHERE NOT EXISTS (SELECT 1 FROM evento v
                      WHERE v.run_id = c.run_id AND v.feature_id = c.feature_id
                        AND v.event_type = 'VOID' AND v.event_id > c.baseline)),
ultimo AS (
    SELECT f.run_id, f.feature_id, f.path, f.op, f.next, f.tipo_next, f.event_id,
           ROW_NUMBER() OVER (PARTITION BY f.run_id, f.feature_id, f.path
                              ORDER BY f.event_id DESC) AS rn
    FROM campo f JOIN viva v
      ON v.run_id = f.run_id AND v.feature_id = f.feature_id AND f.event_id >= v.baseline)
SELECT run_id, feature_id, path, next AS valor, tipo_next AS tipo, event_id AS definido_em
FROM ultimo WHERE rn = 1 AND op = 'set';

-- =====================================================================
-- Consultas de exemplo (:run é o run, :n um event_id usado como corte)
-- =====================================================================

-- Estado de uma feature ao fim do evento :n
-- (o ciclo começa no último BASELINE <= :n; a feature não existe se
--  houver VOID entre esse BASELINE e :n)
-- WITH b AS (SELECT max(event_id) AS baseline FROM evento
--            WHERE run_id = :run AND feature_id = :f
--              AND event_type = 'BASELINE' AND event_id <= :n),
-- ultimo AS (
--   SELECT c.*, ROW_NUMBER() OVER (PARTITION BY path ORDER BY event_id DESC) AS rn
--   FROM campo c, b
--   WHERE c.run_id = :run AND c.feature_id = :f
--     AND c.event_id BETWEEN b.baseline AND :n)
-- SELECT path, next FROM ultimo
-- WHERE rn = 1 AND op = 'set'
--   AND NOT EXISTS (SELECT 1 FROM evento v, b
--                   WHERE v.run_id = :run AND v.feature_id = :f
--                     AND v.event_type = 'VOID'
--                     AND v.event_id > b.baseline AND v.event_id <= :n)
-- ORDER BY path;

-- O que cada evento entre :de e :ate escreveu, com autor, motivo e causa
-- SELECT e.instante, e.feature_id, e.event_type, c.path, c.op, c.next,
--        e.asserted_by, e.reason, e.caused_by
-- FROM evento_legivel e LEFT JOIN campo c USING (event_id)
-- WHERE e.run_id = :run AND e.event_id > :de AND e.event_id <= :ate
-- ORDER BY e.event_id, c.path;

-- Trilha de causa de um evento (subindo pelos caused_by)
-- WITH RECURSIVE trilha(event_id, caused_by, nivel) AS (
--   SELECT event_id, caused_by, 0 FROM evento WHERE event_id = :evento
--   UNION ALL
--   SELECT e.event_id, e.caused_by, t.nivel + 1
--   FROM evento e JOIN trilha t ON e.event_id = t.caused_by)
-- SELECT t.nivel, l.* FROM trilha t JOIN evento_legivel l USING (event_id)
-- ORDER BY t.nivel;

-- Referencial vigente (o ref_id está no airport) e suas cabeceiras
-- SELECT r.ref_id, json_extract(r.corpo, '$.referentes') AS referentes
-- FROM estado_atual s JOIN referencial r ON r.ref_id = s.valor
-- WHERE s.run_id = :run AND s.path = 'referencial.ref_id';
