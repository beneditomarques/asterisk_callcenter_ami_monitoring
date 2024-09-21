CREATE TABLE monitoring_agents (
    uniqueid       TEXT PRIMARY KEY,
    fila           TEXT NOT NULL,
    agente         TEXT NOT NULL,
    ramal          TEXT NOT NULL,
    chamadas       INTEGER DEFAULT 0,
    ultima_chamada TIMESTAMP,
    status         INTEGER DEFAULT 0,
    logado_desde   TIMESTAMP
);