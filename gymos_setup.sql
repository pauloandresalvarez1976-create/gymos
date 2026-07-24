-- ============================================================
--  GymOS — Script de instalación completa
--  Ejecutar en Supabase SQL Editor → Run
--  Crea todas las tablas, índices, datos iniciales y usuario admin
-- ============================================================

-- ── SOCIOS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS socios (
  id                  SERIAL PRIMARY KEY,
  nombre              VARCHAR(100) NOT NULL,
  dni                 VARCHAR(20),
  telefono            VARCHAR(30),
  email               VARCHAR(100),
  plan                VARCHAR(50),
  fecha_inicio        DATE,
  fecha_venc          DATE,
  foto                VARCHAR(200),
  encoding            TEXT,
  activo              INTEGER DEFAULT 1,
  objetivo            VARCHAR(50),
  congelado           INTEGER DEFAULT 0,
  fecha_congelado     DATE,
  dias_congelados     INTEGER,
  peso_objetivo       VARCHAR(10),
  ultimo_resumen_mes  VARCHAR(7),
  ultimo_cumple_anio  INTEGER,
  ultimo_resumen_sem  VARCHAR(8),
  ia_habilitada       INTEGER DEFAULT 0,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── FICHAS MÉDICAS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fichas_medicas (
  id                   SERIAL PRIMARY KEY,
  socio_id             INTEGER UNIQUE,
  fecha_nacimiento     DATE,
  sexo                 VARCHAR(20),
  grupo_sanguineo      VARCHAR(10),
  peso                 VARCHAR(10),
  altura               VARCHAR(10),
  enfermedades         TEXT,
  lesiones             TEXT,
  medicacion           TEXT,
  alergias             TEXT,
  hace_ejercicio       VARCHAR(10),
  autorizacion_medica  VARCHAR(10),
  observaciones        TEXT,
  declaracion_aceptada INTEGER DEFAULT 0,
  declaracion_fecha    TIMESTAMP,
  declaracion_ip       VARCHAR(50),
  created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── PROGRESO ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS progreso (
  id                SERIAL PRIMARY KEY,
  socio_id          INTEGER NOT NULL,
  fecha             DATE DEFAULT CURRENT_DATE,
  peso              VARCHAR(10),
  grasa             VARCHAR(10),
  cintura           VARCHAR(10),
  brazo             VARCHAR(10),
  pecho             VARCHAR(10),
  cadera            VARCHAR(10),
  pierna            VARCHAR(10),
  es_inicial        INTEGER DEFAULT 0,
  comentario_profe  TEXT,
  comentario_fecha  TIMESTAMP,
  storage_path      TEXT,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── USUARIOS ADMIN ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
  id         SERIAL PRIMARY KEY,
  nombre     VARCHAR(100),
  pin        VARCHAR(10),
  rol        VARCHAR(50),
  permisos   TEXT,
  activo     INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── PAGOS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pagos (
  id         SERIAL PRIMARY KEY,
  socio_id   INTEGER,
  monto      INTEGER,
  fecha      DATE DEFAULT CURRENT_DATE,
  metodo     VARCHAR(50),
  plan       VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── INGRESOS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingresos (
  id       SERIAL PRIMARY KEY,
  socio_id INTEGER,
  fecha    DATE DEFAULT CURRENT_DATE,
  hora     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── CLASES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clases (
  id       SERIAL PRIMARY KEY,
  nombre   VARCHAR(100),
  profesor VARCHAR(100),
  dia      VARCHAR(20),
  hora     VARCHAR(10),
  cupo_max INTEGER DEFAULT 20,
  cupo_act INTEGER DEFAULT 0
);

-- ── RESERVAS CLASES ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reservas_clases (
  id            SERIAL PRIMARY KEY,
  socio_id      INTEGER NOT NULL,
  clase_id      INTEGER NOT NULL,
  fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (socio_id, clase_id)
);

-- ── SOLICITUDES RENOVACIÓN ──────────────────────────────────
CREATE TABLE IF NOT EXISTS solicitudes_renovacion (
  id           SERIAL PRIMARY KEY,
  socio_id     INTEGER NOT NULL,
  plan_elegido TEXT,
  monto        TEXT,
  imagen_path  TEXT,
  estado       TEXT DEFAULT 'pendiente',
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── CONFIGURACIÓN ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS config (
  id    SERIAL PRIMARY KEY,
  clave VARCHAR(50) UNIQUE,
  valor VARCHAR(200)
);

-- ── ÍNDICES ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_socios_activo    ON socios(activo);
CREATE INDEX IF NOT EXISTS idx_socios_venc      ON socios(fecha_venc);
CREATE INDEX IF NOT EXISTS idx_pagos_socio      ON pagos(socio_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_socio   ON ingresos(socio_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_fecha   ON ingresos(fecha);
CREATE INDEX IF NOT EXISTS idx_progreso_socio   ON progreso(socio_id);
CREATE INDEX IF NOT EXISTS idx_clases_dia       ON clases(dia);
CREATE INDEX IF NOT EXISTS idx_reservas_clase   ON reservas_clases(clase_id);
CREATE INDEX IF NOT EXISTS idx_reservas_socio   ON reservas_clases(socio_id);

-- ── DATOS INICIALES ─────────────────────────────────────────

-- Usuario administrador por defecto (PIN: 0000 — cambiarlo al entrar)
INSERT INTO usuarios (nombre, pin, rol, permisos, activo)
VALUES ('Administrador', '0000', 'administrador', '{}', 1)
ON CONFLICT DO NOTHING;

-- Configuración básica del gimnasio
INSERT INTO config (clave, valor) VALUES
  ('gym_nombre',       'Mi Gimnasio'),
  ('gym_telefono',     ''),
  ('gym_email',        ''),
  ('gym_direccion',    ''),
  ('smtp_host',        ''),
  ('smtp_port',        '587'),
  ('smtp_user',        ''),
  ('smtp_pass',        ''),
  ('plan_1_nombre',    'Plan Mensual'),
  ('plan_1_precio',    ''),
  ('plan_1_dias',      '30'),
  ('plan_2_nombre',    'Plan Trimestral'),
  ('plan_2_precio',    ''),
  ('plan_2_dias',      '90'),
  ('plan_3_nombre',    'Plan Anual'),
  ('plan_3_precio',    ''),
  ('plan_3_dias',      '365'),
  ('dias_alerta_venc', '7'),
  ('moneda',           'ARS')
ON CONFLICT (clave) DO NOTHING;

-- ============================================================
--  ✅ Listo. Ahora configurá el gimnasio desde el panel admin:
--     1. Cambiá el PIN del administrador
--     2. Completá nombre, logo y datos de contacto
--     3. Configurá los planes y precios
--     4. ¡Empezá a cargar socios!
-- ============================================================
