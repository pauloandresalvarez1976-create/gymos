"""
Script de migración SQLite → Supabase (PostgreSQL)
Correrlo desde tu PC donde está gymos.db
Requiere: pip install psycopg2-binary sqlalchemy
"""
import sqlite3
from sqlalchemy import create_engine, text

# ── CONFIGURACIÓN ─────────────────────────────────────────
SQLITE_PATH = 'gymos.db'
SUPABASE_URL = 'postgresql://postgres.ntvrpmebrnbjrqizqamy:TU_CONTRASEÑA@aws-1-us-west-2.pooler.supabase.com:5432/postgres'
# ─────────────────────────────────────────────────────────

sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
cur = sqlite_conn.cursor()

pg_engine = create_engine(SUPABASE_URL)

with pg_engine.connect() as pg:

    # Migrar socios
    cur.execute("SELECT * FROM socios")
    socios = cur.fetchall()
    for s in socios:
        d = dict(s)
        pg.execute(text("""
            INSERT INTO socios (id, nombre, dni, telefono, email, plan, objetivo,
                fecha_inicio, fecha_venc, foto, activo, congelado, fecha_congelado, dias_congelados)
            VALUES (:id, :nombre, :dni, :telefono, :email, :plan, :objetivo,
                :fecha_inicio, :fecha_venc, :foto, :activo, :congelado, :fecha_congelado, :dias_congelados)
            ON CONFLICT (id) DO NOTHING
        """), d)
    print(f"✅ Socios migrados: {len(socios)}")

    # Migrar pagos
    cur.execute("SELECT * FROM pagos")
    pagos = cur.fetchall()
    for p in pagos:
        d = dict(p)
        pg.execute(text("""
            INSERT INTO pagos (id, socio_id, monto, fecha, metodo, plan)
            VALUES (:id, :socio_id, :monto, :fecha, :metodo, :plan)
            ON CONFLICT (id) DO NOTHING
        """), d)
    print(f"✅ Pagos migrados: {len(pagos)}")

    # Migrar config
    cur.execute("SELECT * FROM config")
    cfgs = cur.fetchall()
    for c in cfgs:
        d = dict(c)
        pg.execute(text("""
            INSERT INTO config (id, clave, valor)
            VALUES (:id, :clave, :valor)
            ON CONFLICT (id) DO NOTHING
        """), d)
    print(f"✅ Config migrada: {len(cfgs)} entradas")

    # Migrar usuarios
    cur.execute("SELECT * FROM usuarios")
    usuarios = cur.fetchall()
    for u in usuarios:
        d = dict(u)
        pg.execute(text("""
            INSERT INTO usuarios (id, nombre, pin, rol, permisos, activo)
            VALUES (:id, :nombre, :pin, :rol, :permisos, :activo)
            ON CONFLICT (id) DO NOTHING
        """), d)
    print(f"✅ Usuarios migrados: {len(usuarios)}")

    # Actualizar secuencias
    pg.execute(text("SELECT setval('socios_id_seq', (SELECT MAX(id) FROM socios))"))
    pg.execute(text("SELECT setval('pagos_id_seq', (SELECT MAX(id) FROM pagos))"))
    pg.execute(text("SELECT setval('config_id_seq', (SELECT MAX(id) FROM config))"))
    pg.execute(text("SELECT setval('usuarios_id_seq', (SELECT MAX(id) FROM usuarios))"))
    pg.commit()

sqlite_conn.close()
print("\n✅ Migración completa.")
