from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date, datetime
import os, base64, json, io, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import qrcode

# Supabase Storage
SUPABASE_URL = 'https://ntvrpmebrnbjrqizqamy.supabase.co'
SUPABASE_SECRET = os.environ.get('SUPABASE_SECRET', '')
FOTOS_BUCKET = 'fotos-progreso'

app = Flask(__name__, static_folder=None)
CORS(app)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, 'gymos.db')
FOTOS_DIR = os.path.join(BASE_DIR, 'static', 'fotos')
os.makedirs(FOTOS_DIR, exist_ok=True)
QR_DIR   = os.path.join(BASE_DIR, 'static', 'qr')
LOGO_DIR = os.path.join(BASE_DIR, 'static', 'logos')
os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(LOGO_DIR, exist_ok=True)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///gymos.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine  = create_engine(DATABASE_URL)
Base    = declarative_base()
Session = sessionmaker(bind=engine)

# ── MODELOS ──────────────────────────────────────────────
class Socio(Base):
    __tablename__ = 'socios'
    id           = Column(Integer, primary_key=True)
    nombre       = Column(String(100), nullable=False)
    dni          = Column(String(20), nullable=True)
    telefono     = Column(String(30))
    email        = Column(String(100))
    plan         = Column(String(50))
    fecha_inicio = Column(Date)
    fecha_venc   = Column(Date)
    foto         = Column(String(200))
    encoding     = Column(Text)
    activo         = Column(Integer, default=1)
    objetivo       = Column(String(50))  # musculacion, perdida_peso, fitness, definicion
    congelado      = Column(Integer, default=0)
    fecha_congelado = Column(Date, nullable=True)
    dias_congelados = Column(Integer, nullable=True)
    peso_objetivo   = Column(String(10), nullable=True)
    ultimo_resumen_mes = Column(String(7), nullable=True)  # 'YYYY-MM'
    created_at     = Column(DateTime, default=datetime.now)

class FichaMedica(Base):
    __tablename__ = 'fichas_medicas'
    id                  = Column(Integer, primary_key=True)
    socio_id            = Column(Integer, unique=True)
    fecha_nacimiento    = Column(Date, nullable=True)
    sexo                = Column(String(20))
    grupo_sanguineo     = Column(String(10))
    peso                = Column(String(10))
    altura              = Column(String(10))
    enfermedades        = Column(Text)
    lesiones            = Column(Text)
    medicacion          = Column(Text)
    alergias            = Column(Text)
    hace_ejercicio      = Column(String(10))
    autorizacion_medica = Column(String(10))
    observaciones       = Column(Text)
    # Declaración jurada
    declaracion_aceptada = Column(Integer, default=0)
    declaracion_fecha    = Column(DateTime, nullable=True)
    declaracion_ip       = Column(String(50))
    created_at          = Column(DateTime, default=datetime.now)
    updated_at          = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Progreso(Base):
    __tablename__ = 'progreso'
    id                = Column(Integer, primary_key=True)
    socio_id          = Column(Integer, nullable=False)
    fecha             = Column(Date, default=date.today)
    peso              = Column(String(10))
    grasa             = Column(String(10))
    cintura           = Column(String(10))
    brazo             = Column(String(10))
    pecho             = Column(String(10))
    cadera            = Column(String(10))
    pierna            = Column(String(10))
    es_inicial        = Column(Integer, default=0)
    comentario_profe  = Column(Text)
    comentario_fecha  = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, default=datetime.now)

class Usuario(Base):
    __tablename__ = 'usuarios'
    id        = Column(Integer, primary_key=True)
    nombre    = Column(String(100))
    pin       = Column(String(10))
    rol       = Column(String(50))  # administrador, encargado, recepcionista
    permisos  = Column(Text)        # JSON con permisos por pantalla
    activo    = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)

class Pago(Base):
    __tablename__ = 'pagos'
    id         = Column(Integer, primary_key=True)
    socio_id   = Column(Integer)
    monto      = Column(Integer)
    fecha      = Column(Date, default=date.today)
    metodo     = Column(String(50))
    plan       = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

class Ingreso(Base):
    __tablename__ = 'ingresos'
    id       = Column(Integer, primary_key=True)
    socio_id = Column(Integer)
    fecha    = Column(Date, default=date.today)
    hora     = Column(DateTime, default=datetime.now)

class Clase(Base):
    __tablename__ = 'clases'
    id       = Column(Integer, primary_key=True)
    nombre   = Column(String(100))
    profesor = Column(String(100))
    dia      = Column(String(20))
    hora     = Column(String(10))
    cupo_max = Column(Integer, default=20)
    cupo_act = Column(Integer, default=0)

class Config(Base):
    __tablename__ = 'config'
    id    = Column(Integer, primary_key=True)
    clave = Column(String(50), unique=True)
    valor = Column(String(200))

Base.metadata.create_all(engine)

def migrate_db():
    """Crea tablas y agrega columnas nuevas compatible con PostgreSQL y SQLite."""
    with engine.connect() as conn:
        # Tablas nuevas
        conn.execute(text("""CREATE TABLE IF NOT EXISTS progreso (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL, fecha DATE,
            peso TEXT, grasa TEXT, cintura TEXT, brazo TEXT, pecho TEXT, cadera TEXT, pierna TEXT,
            es_inicial INTEGER DEFAULT 0,
            comentario_profe TEXT, comentario_fecha TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS pasos (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL,
            fecha DATE,
            pasos INTEGER DEFAULT 0,
            calorias INTEGER DEFAULT 0,
            duracion_seg INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS musculos_sesion (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL,
            fecha DATE,
            musculos TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS hidratacion (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL,
            fecha DATE,
            ml INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS entrenamientos (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL,
            fecha DATE,
            rutina_nombre TEXT,
            dia_nombre TEXT,
            ejercicios_total INTEGER DEFAULT 0,
            series_total INTEGER DEFAULT 0,
            duracion_seg INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS fotos_progreso (
            id SERIAL PRIMARY KEY,
            socio_id INTEGER NOT NULL,
            fecha DATE,
            storage_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS fichas_medicas (
            id SERIAL PRIMARY KEY, socio_id INTEGER UNIQUE,
            fecha_nacimiento DATE, sexo TEXT, grupo_sanguineo TEXT,
            peso TEXT, altura TEXT, enfermedades TEXT, lesiones TEXT,
            medicacion TEXT, alergias TEXT, hace_ejercicio TEXT,
            autorizacion_medica TEXT, observaciones TEXT,
            declaracion_aceptada INTEGER DEFAULT 0,
            declaracion_fecha TIMESTAMP, declaracion_ip TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre TEXT, pin TEXT, rol TEXT, permisos TEXT, activo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        conn.commit()

        # Columnas nuevas (IF NOT EXISTS solo disponible en PostgreSQL)
        migraciones = [
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS plan TEXT",
            "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS congelado INTEGER DEFAULT 0",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS fecha_congelado DATE",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS dias_congelados INTEGER",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS objetivo TEXT",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS peso_objetivo TEXT",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS ultimo_resumen_mes TEXT",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS encoding TEXT",
            "ALTER TABLE socios ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]
        for sql in migraciones:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

        # Admin por defecto si no existe
        try:
            result = conn.execute(text("SELECT id FROM usuarios WHERE rol='administrador'")).fetchone()
            if not result:
                permisos_admin = json.dumps({'ingreso':True,'socios':True,'nuevo':True,'cuotas':True,'agenda':True,'reportes':True,'vencimientos':True,'config':True})
                conn.execute(text("INSERT INTO usuarios (nombre,pin,rol,permisos,activo) VALUES (:n,:p,:r,:pe,:a)"),
                             {'n':'Administrador','p':'1234','r':'administrador','pe':permisos_admin,'a':1})
                conn.commit()
                print("Usuario admin creado: PIN 1234")
        except Exception as e:
            print(f"⚠️ No se pudo crear admin: {e}")

migrate_db()

def init_config():
    session = Session()
    defaults = {'gym_nombre':'Mi Gimnasio','gym_telefono':'','dias_alerta_vencimiento':'7',
                'precio_mensual':'18000','precio_trimestral':'50000','precio_anual':'180000',
                'precio_inscripcion':'5000','dias_alerta':'7',
                'gym_email':'','gym_email_pass':'','gym_email_nombre':'Mi Gimnasio',
                'declaracion_texto':'Declaro bajo juramento que me encuentro en buen estado de salud y en condiciones físicas aptas para realizar actividad física. Eximo al gimnasio y su personal de toda responsabilidad por accidentes, lesiones o problemas de salud que pudieran surgir durante mi entrenamiento, siendo de mi exclusiva responsabilidad informar cualquier condición médica preexistente. Esta declaración tiene carácter de declaración jurada.'}
    for clave, valor in defaults.items():
        c = session.query(Config).filter_by(clave=clave).first()
        if not c:
            session.add(Config(clave=clave, valor=valor))
        # Si existe pero precio_inscripcion nunca se habia guardado con valor real, no tocar
    session.commit(); session.close()

init_config()

def socio_to_dict(s):
    hoy  = date.today()
    venc = s.fecha_venc
    if venc:
        dias   = (venc - hoy).days
        estado = 'al_dia' if dias >= 0 else 'vencido'
    else:
        dias   = None
        estado = 'sin_cuota'
    return {'id':s.id,'nombre':s.nombre,'dni':s.dni,'telefono':s.telefono,
            'email':s.email,'plan':s.plan,
            'fecha_inicio':str(s.fecha_inicio) if s.fecha_inicio else None,
            'fecha_venc':str(s.fecha_venc) if s.fecha_venc else None,
            'foto':s.foto,'activo':s.activo,'estado':estado,'dias_restantes':dias,
            'congelado':s.congelado or 0,'fecha_congelado':str(s.fecha_congelado) if s.fecha_congelado else None,
            'objetivo':s.objetivo or ''}

# ── FRONTEND ─────────────────────────────────────────────
@app.route('/ficha/<int:sid>')
def ficha_window(sid):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'ficha.html')

@app.route('/progreso/<int:sid>')
def progreso_window(sid):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'progreso_admin.html')

@app.route('/socio/<int:sid>')
def pwa_socio(sid):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'socio.html')

@app.route('/sw.js')
def service_worker():
    return send_from_directory(BASE_DIR, 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    return manifest_data(None)

@app.route('/manifest/<int:sid>.json')
def manifest_socio(sid):
    return manifest_data(sid)

def manifest_data(sid):
    session = Session()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    session.close()
    gym_nombre = cfg.get('gym_nombre', 'GymOS')
    gym_logo   = cfg.get('gym_logo', '')
    if gym_logo:
        icons = [
            {'src': f'/static/logos/{gym_logo}', 'sizes': 'any', 'type': 'image/png', 'purpose': 'any maskable'}
        ]
    else:
        icons = [
            {'src': '/static/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/static/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}
        ]
    start_url = f'/socio/{sid}' if sid else '/socio/'
    data = {
        'name': f'{gym_nombre} — Mi Membresía',
        'short_name': gym_nombre,
        'description': f'Tu app de membresía y progreso en {gym_nombre}',
        'start_url': start_url,
        'scope': '/socio/',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#0d0d0d',
        'theme_color': '#FF4500',
        'icons': icons
    }
    from flask import Response
    import json
    return Response(json.dumps(data), mimetype='application/manifest+json')

@app.route('/api/socio/<int:sid>/pwa', methods=['GET'])
def get_socio_pwa(sid):
    """Datos completos del socio para la PWA."""
    session = Session()
    s = session.query(Socio).get(sid)
    if not s or not s.activo:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    pagos = session.query(Pago).filter_by(socio_id=sid).order_by(Pago.fecha.desc()).limit(5).all()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    pagos_list = [{'monto': p.monto, 'fecha': str(p.fecha), 'metodo': p.metodo, 'plan': p.plan} for p in pagos]
    ficha_row = session.execute(text("SELECT altura FROM fichas_medicas WHERE socio_id=:sid LIMIT 1"), {'sid': sid}).fetchone()
    altura = ficha_row[0] if ficha_row and ficha_row[0] else ''
    result = socio_to_dict(s)
    result['pagos'] = pagos_list
    result['gym_nombre'] = cfg.get('gym_nombre', 'Gimnasio')
    result['gym_telefono'] = cfg.get('gym_telefono', '')
    result['gym_email'] = cfg.get('gym_email', '')
    result['gym_logo'] = cfg.get('gym_logo', '')
    result['qr_url'] = f'/qr/socio_{sid}.png'
    result['altura'] = altura
    session.close()
    return jsonify({'ok': True, 'socio': result})

@app.route('/api/socios/<int:sid>/objetivo', methods=['POST'])
def set_objetivo(sid):
    data = request.json
    session = Session()
    s = session.query(Socio).get(sid)
    if not s: session.close(); return jsonify({'ok': False}), 404
    s.objetivo = data.get('objetivo', '')
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/')
def index():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'index.html')

@app.route('/fotos/<path:path>')
def fotos(path):
    return send_from_directory(FOTOS_DIR, path)

@app.route('/qr/<path:path>')
def serve_qr(path):
    return send_from_directory(QR_DIR, path)

# ── SOCIOS ───────────────────────────────────────────────
@app.route('/api/socios', methods=['GET'])
def get_socios():
    session = Session()
    q      = request.args.get('q', '')
    socios = session.query(Socio).filter(Socio.activo == 1)
    if q: socios = socios.filter(Socio.nombre.ilike(f'%{q}%'))
    result = [socio_to_dict(s) for s in socios.all()]
    session.close(); return jsonify(result)

@app.route('/api/socios/<int:sid>', methods=['GET'])
def get_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s: session.close(); return jsonify({'error':'No encontrado'}), 404
    data = socio_to_dict(s); session.close(); return jsonify(data)

@app.route('/api/socios', methods=['POST'])
def crear_socio():
    session = Session()
    data    = request.json
    from dateutil.relativedelta import relativedelta
    inicio  = date.fromisoformat(data.get('fecha_inicio', str(date.today())))
    plan    = data.get('plan', 'Mensual')
    if 'Trimestral' in plan:   venc = inicio + relativedelta(months=3)
    elif 'Anual' in plan:      venc = inicio + relativedelta(years=1)
    else:                      venc = inicio + relativedelta(months=1)
    socio = Socio(nombre=data['nombre'],dni=data.get('dni'),telefono=data.get('telefono'),
                  email=data.get('email'),plan=plan,fecha_inicio=inicio,fecha_venc=venc,activo=1)
    foto_b64 = data.get('foto_base64')
    if foto_b64:
        nombre_foto = f"socio_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
        ruta_foto   = os.path.join(FOTOS_DIR, nombre_foto)
        with open(ruta_foto, 'wb') as f:
            f.write(base64.b64decode(foto_b64.split(',')[-1]))
        socio.foto = nombre_foto
        try:
            socio.encoding = json.dumps(generar_encoding(ruta_foto))
        except Exception as e:
            print(f"Warning facial: {e}")
    session.add(socio); session.commit()
    result = socio_to_dict(socio); session.close()
    return jsonify(result), 201

@app.route('/api/socios/<int:sid>', methods=['PUT'])
def actualizar_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s: session.close(); return jsonify({'error':'No encontrado'}), 404
    data = request.json
    for campo in ['nombre','dni','telefono','email','plan']:
        if campo in data: setattr(s, campo, data[campo])
    if data.get('fecha_venc'):
        s.fecha_venc = date.fromisoformat(data['fecha_venc'])
    foto_b64 = data.get('foto_base64')
    if foto_b64:
        nombre_foto = f"socio_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
        ruta_foto   = os.path.join(FOTOS_DIR, nombre_foto)
        with open(ruta_foto, 'wb') as f:
            f.write(base64.b64decode(foto_b64.split(',')[-1]))
        s.foto = nombre_foto
        try:
            enc = generar_encoding(ruta_foto)
            s.encoding = json.dumps(enc) if enc else None
        except Exception as e:
            print(f"Warning facial update: {e}")
    session.commit(); result = socio_to_dict(s); session.close(); return jsonify(result)

@app.route('/api/socios/<int:sid>', methods=['DELETE'])
def eliminar_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if s: s.activo = 0; session.commit()
    session.close(); return jsonify({'ok': True})

# ── PAGOS ────────────────────────────────────────────────
@app.route('/api/pagos', methods=['POST'])
def registrar_pago():
    session = Session()
    data    = request.json
    from dateutil.relativedelta import relativedelta
    pago = Pago(socio_id=data['socio_id'],monto=data.get('monto',0),
                metodo=data.get('metodo','efectivo'),plan=data.get('plan',''),fecha=date.today())
    session.add(pago)
    socio = session.query(Socio).get(data['socio_id'])
    if socio:
        # Usar el plan enviado desde el frontend; si no, el plan actual del socio
        plan = data.get('plan') or socio.plan or ''
        if plan and plan != 'Inscripcion':
            socio.plan = plan  # actualizar plan del socio
        base = max(socio.fecha_venc or date.today(), date.today())
        if 'Trimestral' in plan:    socio.fecha_venc = base + relativedelta(months=3)
        elif 'Anual' in plan:       socio.fecha_venc = base + relativedelta(years=1)
        elif 'Inscripcion' in plan: pass  # inscripción no extiende vencimiento
        else:                       socio.fecha_venc = base + relativedelta(months=1)
    session.commit()
    result = socio_to_dict(socio) if socio else {}
    session.close()
    return jsonify({'ok': True, 'socio': result})

@app.route('/api/pagos/<int:socio_id>', methods=['GET'])
def get_pagos_socio(socio_id):
    session = Session()
    pagos  = session.query(Pago).filter_by(socio_id=socio_id).order_by(Pago.fecha.desc()).all()
    result = [{'id':p.id,'monto':p.monto,'fecha':str(p.fecha),'metodo':p.metodo,'plan':p.plan} for p in pagos]
    session.close(); return jsonify(result)

# ── CONGELAMIENTO ───────────────────────────────────────
@app.route('/api/socios/<int:sid>/congelar', methods=['POST'])
def congelar_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'error':'No encontrado'}), 404
    if s.congelado:
        session.close(); return jsonify({'error':'Ya está congelado'}), 400
    hoy = date.today()
    dias = (s.fecha_venc - hoy).days if s.fecha_venc else 0
    s.congelado = 1
    s.fecha_congelado = hoy
    s.dias_congelados = max(dias, 0)
    session.commit()
    result = socio_to_dict(s); session.close()
    return jsonify({'ok': True, 'socio': result})

@app.route('/api/socios/<int:sid>/descongelar', methods=['POST'])
def descongelar_socio(sid):
    from dateutil.relativedelta import relativedelta
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'error':'No encontrado'}), 404
    if not s.congelado:
        session.close(); return jsonify({'error':'No está congelado'}), 400
    dias = s.dias_congelados or 0
    s.fecha_venc = date.today() + relativedelta(days=dias)
    s.congelado = 0
    s.fecha_congelado = None
    s.dias_congelados = None
    session.commit()
    result = socio_to_dict(s); session.close()
    return jsonify({'ok': True, 'socio': result})

# ── VENCIMIENTOS ─────────────────────────────────────────
# ── USUARIOS / ROLES ─────────────────────────────────────
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    session = Session()
    users = session.query(Usuario).filter_by(activo=1).all()
    result = [{'id':u.id,'nombre':u.nombre,'rol':u.rol,'permisos':json.loads(u.permisos or '{}')} for u in users]
    session.close()
    return jsonify(result)

@app.route('/api/usuarios/login', methods=['POST'])
def login_usuario():
    data = request.json
    session = Session()
    u = session.query(Usuario).filter_by(id=data.get('id'), activo=1).first()
    if not u or u.pin != str(data.get('pin','')):
        session.close(); return jsonify({'ok':False,'error':'PIN incorrecto'}), 401
    result = {'id':u.id,'nombre':u.nombre,'rol':u.rol,'permisos':json.loads(u.permisos or '{}')}
    session.close()
    return jsonify({'ok':True,'usuario':result})

@app.route('/api/usuarios', methods=['POST'])
def crear_usuario():
    data = request.json
    session = Session()
    permisos_default = {
        'administrador': {'ingreso':True,'socios':True,'nuevo':True,'cuotas':True,'agenda':True,'reportes':True,'vencimientos':True,'config':True},
        'encargado':     {'ingreso':True,'socios':True,'nuevo':True,'cuotas':True,'agenda':True,'reportes':True,'vencimientos':True,'config':False},
        'recepcionista': {'ingreso':True,'socios':True,'nuevo':False,'cuotas':True,'agenda':False,'reportes':False,'vencimientos':True,'config':False},
    }
    rol = data.get('rol','recepcionista')
    permisos = json.dumps(data.get('permisos') or permisos_default.get(rol,{}))
    u = Usuario(nombre=data['nombre'], pin=data['pin'], rol=rol, permisos=permisos)
    session.add(u)
    session.commit()
    result = {'id':u.id,'nombre':u.nombre,'rol':u.rol,'permisos':json.loads(u.permisos)}
    session.close()
    return jsonify({'ok':True,'usuario':result})

@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
def editar_usuario(uid):
    data = request.json
    session = Session()
    u = session.query(Usuario).get(uid)
    if not u: session.close(); return jsonify({'ok':False}), 404
    if 'nombre' in data: u.nombre = data['nombre']
    if 'pin' in data and data['pin']: u.pin = data['pin']
    if 'rol' in data: u.rol = data['rol']
    if 'permisos' in data: u.permisos = json.dumps(data['permisos'])
    session.commit(); session.close()
    return jsonify({'ok':True})

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
def eliminar_usuario(uid):
    data = request.json or {}
    session = Session()
    u = session.query(Usuario).get(uid)
    if not u: session.close(); return jsonify({'ok':False}), 404
    # No eliminar el último admin
    if u.rol == 'administrador':
        count = session.query(Usuario).filter_by(rol='administrador', activo=1).count()
        if count <= 1:
            session.close(); return jsonify({'ok':False,'error':'Debe haber al menos un administrador'}), 400
    u.activo = 0
    session.commit(); session.close()
    return jsonify({'ok':True})

# ── QR ACCESO ────────────────────────────────────────────
@app.route('/api/socios/<int:sid>/qr', methods=['GET'])
def get_qr_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    session.close()
    if not s:
        return jsonify({'error': 'Socio no encontrado'}), 404
    # Generar QR si no existe
    qr_filename = f'socio_{sid}.png'
    qr_path = os.path.join(QR_DIR, qr_filename)
    if not os.path.exists(qr_path):
        qr_data = f'GYMOS:SOCIO:{sid}'
        qr = qrcode.QRCode(version=1, box_size=10, border=4,
                            error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img.save(qr_path)
    return jsonify({'ok': True, 'qr_url': f'/qr/{qr_filename}', 'socio': s.nombre})

@app.route('/api/qr/escanear', methods=['POST'])
def escanear_qr():
    """Recibe el contenido del QR escaneado y devuelve el socio."""
    data = request.json
    qr_data = data.get('qr_data', '')
    if not qr_data.startswith('GYMOS:SOCIO:'):
        return jsonify({'ok': False, 'error': 'QR inválido'}), 400
    try:
        sid = int(qr_data.replace('GYMOS:SOCIO:', ''))
    except:
        return jsonify({'ok': False, 'error': 'QR inválido'}), 400
    session = Session()
    s = session.query(Socio).get(sid)
    if not s or not s.activo:
        session.close()
        return jsonify({'ok': False, 'error': 'Socio no encontrado o inactivo'}), 404
    # Registrar ingreso
    ingreso = Ingreso(socio_id=sid, fecha=date.today())
    session.add(ingreso)
    session.commit()
    result = socio_to_dict(s)
    session.close()
    return jsonify({'ok': True, 'socio': result})

# ── COMPROBANTE EMAIL ────────────────────────────────────
def enviar_email(destinatario, asunto, html, session, adjunto_path=None, adjunto_nombre=None):
    """Envía un email usando la config SMTP guardada. Opcionalmente adjunta un archivo."""
    from email.mime.base import MIMEBase
    from email import encoders
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    gym_email      = cfg.get('gym_email', '')
    gym_email_pass = cfg.get('gym_email_pass', '')
    gym_nombre     = cfg.get('gym_email_nombre') or cfg.get('gym_nombre', 'Gimnasio')
    if not gym_email or not gym_email_pass:
        raise Exception('Email no configurado en Ajustes')
    msg = MIMEMultipart('mixed')
    msg['Subject'] = asunto
    msg['From']    = f'{gym_nombre} <{gym_email}>'
    msg['To']      = destinatario
    msg.attach(MIMEText(html, 'html'))
    if adjunto_path and os.path.exists(adjunto_path):
        with open(adjunto_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        nombre = adjunto_nombre or os.path.basename(adjunto_path)
        part.add_header('Content-Disposition', f'attachment; filename="{nombre}"')
        msg.attach(part)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gym_email, gym_email_pass)
        server.sendmail(gym_email, destinatario, msg.as_string())

MESES_ES = ['', 'enero','febrero','marzo','abril','mayo','junio',
            'julio','agosto','septiembre','octubre','noviembre','diciembre']

def enviar_resumenes_mensuales():
    """Al arrancar el servidor, manda un resumen de progreso a los socios
    que cargaron mediciones este mes y todavía no recibieron el resumen."""
    session = Session()
    try:
        hoy = date.today()
        mes_actual = hoy.strftime('%Y-%m')
        inicio_mes = date(hoy.year, hoy.month, 1)
        cfg = {c.clave: c.valor for c in session.query(Config).all()}
        gym_email = cfg.get('gym_email', '')
        if not gym_email:
            session.close(); return  # sin email configurado, no hay nada para enviar
        gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
        socios = session.query(Socio).filter(Socio.activo == 1).all()
        for s in socios:
            if not s.email:
                continue
            if s.ultimo_resumen_mes == mes_actual:
                continue
            registros_mes = session.query(Progreso).filter(
                Progreso.socio_id == s.id, Progreso.fecha >= inicio_mes
            ).order_by(Progreso.fecha.asc()).all()
            if not registros_mes:
                continue
            pesos = [float(r.peso) for r in registros_mes if r.peso]
            if len(pesos) >= 2 and pesos[-1] != pesos[0]:
                delta = pesos[-1] - pesos[0]
                delta_txt = f"{'bajaste' if delta < 0 else 'subiste'} {abs(delta):.1f}kg"
            elif pesos:
                delta_txt = f"te mantuviste en {pesos[-1]:.1f}kg"
            else:
                delta_txt = "cargaste nuevos datos"
            mes_nombre = MESES_ES[hoy.month]
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
              <div style="background:#FF4500;padding:24px;text-align:center">
                <h2 style="margin:0;color:white;font-size:20px">📈 {gym_nombre}</h2>
                <p style="margin:6px 0 0;color:#fff9;font-size:13px">Tu resumen de progreso de {mes_nombre}</p>
              </div>
              <div style="padding:24px;text-align:center">
                <p style="font-size:15px">Hola <strong>{s.nombre.split()[0]}</strong>,</p>
                <p style="color:#ccc;font-size:14px">Este mes {delta_txt} y cargaste <strong>{len(registros_mes)}</strong> registro(s) de progreso.</p>
                <p style="color:#aaa;font-size:13px">Entrá a tu app para ver el detalle completo y tu gráfico de evolución.</p>
                <p style="color:#666;font-size:11px;margin-top:20px">Seguí así! 💪</p>
              </div>
            </div>"""
            try:
                enviar_email(s.email, f'Tu resumen de progreso — {gym_nombre}', html, session)
                s.ultimo_resumen_mes = mes_actual
                session.commit()
            except Exception as e:
                print(f"⚠️  No se pudo enviar resumen mensual a {s.nombre}: {e}")
    finally:
        session.close()

@app.route('/api/pagos/comprobante', methods=['POST'])
def enviar_comprobante():
    session = Session()
    data     = request.json
    socio_id = data.get('socio_id')
    socio    = session.query(Socio).get(socio_id) if socio_id else None
    if not socio:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    if not socio.email:
        session.close(); return jsonify({'ok': False, 'error': 'El socio no tiene email registrado'}), 400
    ultimo_pago = session.query(Pago).filter_by(socio_id=socio_id).order_by(Pago.fecha.desc()).first()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
    monto  = f"${int(ultimo_pago.monto):,}".replace(',','.') if ultimo_pago else '$0'
    metodo = ultimo_pago.metodo if ultimo_pago else '—'
    plan   = ultimo_pago.plan   if ultimo_pago else '—'
    fecha  = str(ultimo_pago.fecha) if ultimo_pago else '—'
    venc   = str(socio.fecha_venc)  if socio.fecha_venc else '—'
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
      <div style="background:#FF4500;padding:24px;text-align:center">
        <h2 style="margin:0;color:white;font-size:20px">🏋️ {gym_nombre}</h2>
        <p style="margin:6px 0 0;color:#fff9;font-size:13px">Comprobante de pago</p>
      </div>
      <div style="padding:24px">
        <p style="font-size:15px">Hola <strong>{socio.nombre.split()[0]}</strong>,</p>
        <p style="color:#aaa;font-size:13px">Te confirmamos el siguiente pago registrado:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="border-bottom:1px solid #333"><td style="padding:10px 0;color:#888;font-size:12px">Plan</td><td style="padding:10px 0;text-align:right;font-size:13px">{plan}</td></tr>
          <tr style="border-bottom:1px solid #333"><td style="padding:10px 0;color:#888;font-size:12px">Monto</td><td style="padding:10px 0;text-align:right;font-size:15px;color:#FF4500;font-weight:bold">{monto}</td></tr>
          <tr style="border-bottom:1px solid #333"><td style="padding:10px 0;color:#888;font-size:12px">Método</td><td style="padding:10px 0;text-align:right;font-size:13px">{metodo.capitalize()}</td></tr>
          <tr style="border-bottom:1px solid #333"><td style="padding:10px 0;color:#888;font-size:12px">Fecha</td><td style="padding:10px 0;text-align:right;font-size:13px">{fecha}</td></tr>
          <tr><td style="padding:10px 0;color:#888;font-size:12px">Membresía válida hasta</td><td style="padding:10px 0;text-align:right;font-size:13px;color:#00FF88">{venc}</td></tr>
        </table>
        <p style="color:#666;font-size:11px;margin-top:20px;text-align:center">Gracias por entrenar con nosotros 💪</p>
      </div>
    </div>"""
    try:
        enviar_email(socio.email, f'Comprobante de pago — {gym_nombre}', html, session)
        session.close()
        return jsonify({'ok': True, 'mensaje': f'Comprobante enviado a {socio.email}'})
    except Exception as e:
        session.close()
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── LOGO ─────────────────────────────────────────────────
@app.route('/api/config/logo', methods=['POST'])
def subir_logo():
    if 'logo' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400
    file = request.files['logo']
    if not file.filename: return jsonify({'ok': False}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.svg', '.webp']:
        return jsonify({'ok': False, 'error': 'Formato no soportado'}), 400
    filename = f'logo{ext}'
    file.save(os.path.join(LOGO_DIR, filename))
    # Guardar en config
    session = Session()
    cfg = session.query(Config).filter_by(clave='gym_logo').first()
    if cfg: cfg.valor = filename
    else: session.add(Config(clave='gym_logo', valor=filename))
    session.commit(); session.close()
    return jsonify({'ok': True, 'filename': filename})

@app.route('/api/config/logo', methods=['DELETE'])
def quitar_logo():
    session = Session()
    cfg = session.query(Config).filter_by(clave='gym_logo').first()
    if cfg:
        # Eliminar archivo
        path = os.path.join(LOGO_DIR, cfg.valor)
        if os.path.exists(path): os.remove(path)
        cfg.valor = ''
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/static/logos/<path:path>')
def serve_logo(path):
    return send_from_directory(LOGO_DIR, path)

# ── FICHA MÉDICA ─────────────────────────────────────────
@app.route('/api/socios/<int:sid>/ficha', methods=['GET'])
def get_ficha(sid):
    session = Session()
    ficha = session.query(FichaMedica).filter_by(socio_id=sid).first()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    result = {}
    if ficha:
        result = {
            'socio_id': ficha.socio_id,
            'fecha_nacimiento': str(ficha.fecha_nacimiento) if ficha.fecha_nacimiento else '',
            'sexo': ficha.sexo or '',
            'grupo_sanguineo': ficha.grupo_sanguineo or '',
            'peso': ficha.peso or '',
            'altura': ficha.altura or '',
            'enfermedades': ficha.enfermedades or '',
            'lesiones': ficha.lesiones or '',
            'medicacion': ficha.medicacion or '',
            'alergias': ficha.alergias or '',
            'hace_ejercicio': ficha.hace_ejercicio or '',
            'autorizacion_medica': ficha.autorizacion_medica or '',
            'observaciones': ficha.observaciones or '',
            'declaracion_aceptada': ficha.declaracion_aceptada or 0,
            'declaracion_fecha': str(ficha.declaracion_fecha) if ficha.declaracion_fecha else '',
        }
    session.close()
    return jsonify({'ok': True, 'ficha': result, 'declaracion_texto': cfg.get('declaracion_texto','')})

@app.route('/api/socios/<int:sid>/ficha', methods=['POST'])
def guardar_ficha(sid):
    data = request.json
    session = Session()
    try:
        existe = session.execute(text("SELECT id FROM fichas_medicas WHERE socio_id=:sid LIMIT 1"), {'sid': sid}).fetchone()
        campos = ['sexo','grupo_sanguineo','peso','altura','enfermedades',
                  'lesiones','medicacion','alergias','hace_ejercicio',
                  'autorizacion_medica','observaciones','fecha_nacimiento']
        vals = {c: data.get(c, '') for c in campos}
        vals['sid'] = sid
        decl_aceptada = 1 if data.get('declaracion_aceptada') else 0
        decl_fecha = datetime.now() if decl_aceptada else None
        decl_ip = request.remote_addr if decl_aceptada else None
        vals['decl_aceptada'] = decl_aceptada
        vals['decl_fecha'] = decl_fecha
        vals['decl_ip'] = decl_ip
        if existe:
            session.execute(text("""
                UPDATE fichas_medicas SET
                    sexo=:sexo, grupo_sanguineo=:grupo_sanguineo, peso=:peso, altura=:altura,
                    enfermedades=:enfermedades, lesiones=:lesiones, medicacion=:medicacion,
                    alergias=:alergias, hace_ejercicio=:hace_ejercicio,
                    autorizacion_medica=:autorizacion_medica, observaciones=:observaciones,
                    fecha_nacimiento=:fecha_nacimiento,
                    declaracion_aceptada=:decl_aceptada, declaracion_fecha=:decl_fecha,
                    declaracion_ip=:decl_ip
                WHERE socio_id=:sid
            """), vals)
        else:
            session.execute(text("""
                INSERT INTO fichas_medicas
                    (socio_id, sexo, grupo_sanguineo, peso, altura, enfermedades, lesiones,
                     medicacion, alergias, hace_ejercicio, autorizacion_medica, observaciones,
                     fecha_nacimiento, declaracion_aceptada, declaracion_fecha, declaracion_ip)
                VALUES
                    (:sid, :sexo, :grupo_sanguineo, :peso, :altura, :enfermedades, :lesiones,
                     :medicacion, :alergias, :hace_ejercicio, :autorizacion_medica, :observaciones,
                     :fecha_nacimiento, :decl_aceptada, :decl_fecha, :decl_ip)
            """), vals)
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({'ok': False, 'error': str(e)}), 500
    session.close()
    return jsonify({'ok': True})

# ── PROGRESO (peso, medidas, evolución) ──────────────────
@app.route('/api/socios/<int:sid>/progreso', methods=['GET'])
def get_progreso(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    registros = session.query(Progreso).filter_by(socio_id=sid).order_by(Progreso.fecha.asc(), Progreso.id.asc()).all()
    result = [{
        'id': r.id, 'fecha': str(r.fecha), 'peso': r.peso, 'grasa': r.grasa,
        'cintura': r.cintura, 'brazo': r.brazo, 'pecho': r.pecho,
        'cadera': r.cadera, 'pierna': r.pierna, 'es_inicial': r.es_inicial or 0,
        'comentario_profe': r.comentario_profe or '',
        'comentario_fecha': str(r.comentario_fecha) if r.comentario_fecha else ''
    } for r in registros]
    peso_objetivo = s.peso_objetivo
    objetivo = s.objetivo or ''
    session.close()
    return jsonify({'ok': True, 'registros': result, 'peso_objetivo': peso_objetivo, 'objetivo': objetivo})

@app.route('/api/socios/<int:sid>/progreso', methods=['POST'])
def add_progreso(sid):
    data = request.json or {}
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    if not data.get('peso'):
        session.close(); return jsonify({'ok': False, 'error': 'El peso es obligatorio'}), 400
    existe_inicial = session.query(Progreso).filter_by(socio_id=sid, es_inicial=1).first()
    fecha = date.today()
    if data.get('fecha'):
        try: fecha = date.fromisoformat(data['fecha'])
        except: pass
    r = Progreso(
        socio_id=sid, fecha=fecha,
        peso=str(data.get('peso')) if data.get('peso') else None,
        grasa=str(data.get('grasa')) if data.get('grasa') else None,
        cintura=str(data.get('cintura')) if data.get('cintura') else None,
        brazo=str(data.get('brazo')) if data.get('brazo') else None,
        pecho=str(data.get('pecho')) if data.get('pecho') else None,
        cadera=str(data.get('cadera')) if data.get('cadera') else None,
        pierna=str(data.get('pierna')) if data.get('pierna') else None,
        es_inicial=0 if existe_inicial else 1
    )
    session.add(r)
    session.commit()
    rid = r.id
    session.close()
    return jsonify({'ok': True, 'id': rid})

@app.route('/api/socios/<int:sid>/progreso/<int:rid>', methods=['DELETE'])
def borrar_progreso(sid, rid):
    session = Session()
    r = session.query(Progreso).get(rid)
    if not r or r.socio_id != sid:
        session.close(); return jsonify({'ok': False, 'error': 'Registro no encontrado'}), 404
    session.delete(r)
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/progreso/objetivo', methods=['POST'])
def set_peso_objetivo(sid):
    data = request.json or {}
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    s.peso_objetivo = str(data.get('peso_objetivo')) if data.get('peso_objetivo') else None
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/progreso/<int:rid>/comentario', methods=['POST'])
def comentar_progreso(sid, rid):
    data = request.json or {}
    session = Session()
    r = session.query(Progreso).get(rid)
    if not r or r.socio_id != sid:
        session.close(); return jsonify({'ok': False, 'error': 'Registro no encontrado'}), 404
    r.comentario_profe = data.get('comentario', '')
    r.comentario_fecha = datetime.now()
    session.commit(); session.close()
    return jsonify({'ok': True})

# ── PODÓMETRO ─────────────────────────────────────────────
@app.route('/api/socios/<int:sid>/pasos', methods=['GET'])
def get_pasos(sid):
    session = Session()
    rows = session.execute(text(
        "SELECT id, fecha, pasos, calorias, duracion_seg FROM pasos WHERE socio_id=:sid ORDER BY fecha DESC, id DESC LIMIT 30"
    ), {'sid': sid}).fetchall()
    session.close()
    return jsonify({'ok': True, 'sesiones': [
        {'id': r[0], 'fecha': str(r[1]), 'pasos': r[2], 'calorias': r[3], 'duracion_seg': r[4]}
        for r in rows
    ]})

@app.route('/api/socios/<int:sid>/pasos', methods=['POST'])
def add_pasos(sid):
    data = request.json or {}
    pasos = int(data.get('pasos', 0))
    calorias = int(data.get('calorias', 0))
    duracion_seg = int(data.get('duracion_seg', 0))
    fecha = data.get('fecha', date.today().isoformat())
    if pasos < 1:
        return jsonify({'ok': False, 'error': 'Sin pasos registrados'}), 400
    session = Session()
    session.execute(text(
        "INSERT INTO pasos (socio_id, fecha, pasos, calorias, duracion_seg) VALUES (:sid, :f, :p, :c, :d)"
    ), {'sid': sid, 'f': fecha, 'p': pasos, 'c': calorias, 'd': duracion_seg})
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/pasos/<int:rid>', methods=['DELETE'])
def borrar_pasos(sid, rid):
    session = Session()
    session.execute(text("DELETE FROM pasos WHERE id=:id AND socio_id=:sid"), {'id': rid, 'sid': sid})
    session.commit(); session.close()
    return jsonify({'ok': True})

# ── MÚSCULOS TRABAJADOS ──────────────────────────────────
@app.route('/api/socios/<int:sid>/musculos', methods=['GET'])
def get_musculos(sid):
    session = Session()
    rows = session.execute(text(
        "SELECT id, fecha, musculos FROM musculos_sesion WHERE socio_id=:sid ORDER BY fecha DESC, id DESC LIMIT 60"
    ), {'sid': sid}).fetchall()
    session.close()
    return jsonify({'ok': True, 'sesiones': [
        {'id': r[0], 'fecha': str(r[1]), 'musculos': r[2].split(',') if r[2] else []}
        for r in rows
    ]})

@app.route('/api/socios/<int:sid>/musculos', methods=['POST'])
def add_musculos(sid):
    data = request.json or {}
    musculos = data.get('musculos', [])
    fecha = data.get('fecha', date.today().isoformat())
    if not musculos:
        return jsonify({'ok': False, 'error': 'Sin músculos seleccionados'}), 400
    session = Session()
    session.execute(text(
        "INSERT INTO musculos_sesion (socio_id, fecha, musculos) VALUES (:sid, :f, :m)"
    ), {'sid': sid, 'f': fecha, 'm': ','.join(musculos)})
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/musculos/<int:rid>', methods=['DELETE'])
def borrar_musculos(sid, rid):
    session = Session()
    session.execute(text("DELETE FROM musculos_sesion WHERE id=:id AND socio_id=:sid"), {'id': rid, 'sid': sid})
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/musculos/historial', methods=['GET'])
def get_musculos_historial(sid):
    """Para el admin — frecuencia de cada músculo"""
    session = Session()
    rows = session.execute(text(
        "SELECT musculos FROM musculos_sesion WHERE socio_id=:sid"
    ), {'sid': sid}).fetchall()
    session.close()
    frecuencia = {}
    for r in rows:
        for m in (r[0].split(',') if r[0] else []):
            frecuencia[m] = frecuencia.get(m, 0) + 1
    return jsonify({'ok': True, 'frecuencia': frecuencia})

# ── HIDRATACIÓN ──────────────────────────────────────────────
@app.route('/api/socios/<int:sid>/hidratacion', methods=['GET'])
def get_hidratacion(sid):
    """Devuelve los registros de hidratación de los últimos 30 días"""
    session = Session()
    rows = session.execute(text(
        "SELECT id, fecha, ml FROM hidratacion WHERE socio_id=:sid ORDER BY fecha DESC LIMIT 30"
    ), {'sid': sid}).fetchall()
    session.close()
    return jsonify({'ok': True, 'registros': [
        {'id': r[0], 'fecha': str(r[1]), 'ml': r[2]} for r in rows
    ]})

@app.route('/api/socios/<int:sid>/hidratacion', methods=['POST'])
def set_hidratacion(sid):
    """Upsert: actualiza el registro del día o lo crea"""
    data = request.json
    fecha = data.get('fecha', date.today().isoformat())
    ml = int(data.get('ml', 0))
    if ml < 0:
        ml = 0
    session = Session()
    existing = session.execute(text(
        "SELECT id FROM hidratacion WHERE socio_id=:sid AND fecha=:f"
    ), {'sid': sid, 'f': fecha}).fetchone()
    if existing:
        session.execute(text(
            "UPDATE hidratacion SET ml=:ml WHERE id=:id"
        ), {'ml': ml, 'id': existing[0]})
    else:
        session.execute(text(
            "INSERT INTO hidratacion (socio_id, fecha, ml) VALUES (:sid, :f, :ml)"
        ), {'sid': sid, 'f': fecha, 'ml': ml})
    session.commit(); session.close()
    return jsonify({'ok': True, 'ml': ml})

# ── ENTRENAMIENTOS ───────────────────────────────────────────
@app.route('/api/socios/<int:sid>/entrenamientos', methods=['GET'])
def get_entrenamientos(sid):
    session = Session()
    rows = session.execute(text(
        """SELECT id, fecha, rutina_nombre, dia_nombre, ejercicios_total, series_total, duracion_seg
           FROM entrenamientos WHERE socio_id=:sid ORDER BY fecha DESC, id DESC LIMIT 30"""
    ), {'sid': sid}).fetchall()
    session.close()
    return jsonify({'ok': True, 'entrenamientos': [
        {'id': r[0], 'fecha': str(r[1]), 'rutina_nombre': r[2], 'dia_nombre': r[3],
         'ejercicios_total': r[4], 'series_total': r[5], 'duracion_seg': r[6]}
        for r in rows
    ]})

@app.route('/api/socios/<int:sid>/entrenamientos', methods=['POST'])
def add_entrenamiento(sid):
    data = request.json
    fecha = data.get('fecha', date.today().isoformat())
    session = Session()
    session.execute(text(
        """INSERT INTO entrenamientos
           (socio_id, fecha, rutina_nombre, dia_nombre, ejercicios_total, series_total, duracion_seg)
           VALUES (:sid, :f, :rn, :dn, :et, :st, :ds)"""
    ), {
        'sid': sid, 'f': fecha,
        'rn': data.get('rutina_nombre', ''),
        'dn': data.get('dia_nombre', ''),
        'et': int(data.get('ejercicios_total', 0)),
        'st': int(data.get('series_total', 0)),
        'ds': int(data.get('duracion_seg', 0))
    })
    session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/socios/<int:sid>/entrenamientos/<int:rid>', methods=['DELETE'])
def borrar_entrenamiento(sid, rid):
    session = Session()
    session.execute(text("DELETE FROM entrenamientos WHERE id=:id AND socio_id=:sid"), {'id': rid, 'sid': sid})
    session.commit(); session.close()
    return jsonify({'ok': True})

# ── FOTOS PROGRESO ───────────────────────────────────────────
@app.route('/api/socios/<int:sid>/fotos_progreso', methods=['GET'])
def get_fotos_progreso(sid):
    session = Session()
    rows = session.execute(text(
        "SELECT id, fecha, storage_path FROM fotos_progreso WHERE socio_id=:sid ORDER BY fecha DESC"
    ), {'sid': sid}).fetchall()
    session.close()
    return jsonify({'ok': True, 'fotos': [
        {'id': r[0], 'fecha': str(r[1]), 'storage_path': r[2]} for r in rows
    ]})

@app.route('/api/socios/<int:sid>/fotos_progreso/upload', methods=['POST'])
def upload_foto_progreso(sid):
    """Recibe imagen base64 del frontend, la sube a Supabase Storage, guarda el path en DB"""
    data = request.json
    imagen_b64 = data.get('imagen_b64', '')
    fecha = data.get('fecha', date.today().isoformat())
    if not imagen_b64:
        return jsonify({'ok': False, 'error': 'Sin imagen'}), 400

    # Decodificar base64
    if ',' in imagen_b64:
        imagen_b64 = imagen_b64.split(',')[1]
    imagen_bytes = base64.b64decode(imagen_b64)

    # Path en Storage: socio_id/fecha_timestamp.jpg
    import time
    nombre_archivo = str(sid) + '/' + fecha + '_' + str(int(time.time())) + '.jpg'
    storage_url = SUPABASE_URL + '/storage/v1/object/' + FOTOS_BUCKET + '/' + nombre_archivo

    # Subir a Supabase Storage
    headers = {
        'Authorization': 'Bearer ' + SUPABASE_SECRET,
        'Content-Type': 'image/jpeg',
        'x-upsert': 'true'
    }
    try:
        resp = requests.post(storage_url, headers=headers, data=imagen_bytes, timeout=30)
        if resp.status_code not in (200, 201):
            return jsonify({'ok': False, 'error': resp.text}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    # Guardar path en DB
    session = Session()
    session.execute(text(
        "INSERT INTO fotos_progreso (socio_id, fecha, storage_path) VALUES (:sid, :f, :sp)"
    ), {'sid': sid, 'f': fecha, 'sp': nombre_archivo})
    session.commit(); session.close()
    return jsonify({'ok': True, 'storage_path': nombre_archivo})

@app.route('/api/socios/<int:sid>/fotos_progreso/<int:fid>', methods=['DELETE'])
def borrar_foto_progreso(sid, fid):
    session = Session()
    row = session.execute(text(
        "SELECT storage_path FROM fotos_progreso WHERE id=:id AND socio_id=:sid"
    ), {'id': fid, 'sid': sid}).fetchone()
    if row:
        # Borrar de Supabase Storage
        storage_url = SUPABASE_URL + '/storage/v1/object/' + FOTOS_BUCKET + '/' + row[0]
        try:
            requests.delete(storage_url, headers={'Authorization': 'Bearer ' + SUPABASE_SECRET}, timeout=10)
        except: pass
        session.execute(text("DELETE FROM fotos_progreso WHERE id=:id AND socio_id=:sid"), {'id': fid, 'sid': sid})
        session.commit()
    session.close()
    return jsonify({'ok': True})


# ── DESERCIÓN TEMPRANA ───────────────────────────────────────
@app.route('/api/desercion', methods=['GET'])
def get_desercion():
    """Socios activos sin ninguna actividad en los últimos N días"""
    dias = int(request.args.get('dias', 14))
    session = Session()
    socios = session.execute(text(
        "SELECT id, nombre, telefono, objetivo FROM socios WHERE activo=true ORDER BY nombre"
    )).fetchall()

    resultado = []
    for s in socios:
        sid = s[0]
        # Última actividad: máximo entre pasos, musculos y entrenamientos
        ultima = session.execute(text("""
            SELECT MAX(ultima) FROM (
                SELECT MAX(fecha) as ultima FROM pasos WHERE socio_id=:sid
                UNION ALL
                SELECT MAX(fecha) as ultima FROM musculos_sesion WHERE socio_id=:sid
                UNION ALL
                SELECT MAX(fecha) as ultima FROM entrenamientos WHERE socio_id=:sid
            ) t
        """), {'sid': sid}).scalar()

        if ultima is None:
            dias_inactivo = 9999  # nunca registró actividad
        else:
            dias_inactivo = (date.today() - ultima).days

        if dias_inactivo >= dias:
            resultado.append({
                'id': sid,
                'nombre': s[1],
                'telefono': s[2] or '',
                'objetivo': s[3] or '',
                'dias_inactivo': dias_inactivo,
                'ultima_actividad': str(ultima) if ultima else None
            })

    session.close()
    resultado.sort(key=lambda x: x['dias_inactivo'], reverse=True)
    return jsonify({'ok': True, 'socios': resultado})

@app.route('/api/socios/<int:sid>/enviar_app', methods=['POST'])def enviar_app_socio(sid):
    data = request.json
    email  = data.get('email','')
    nombre = data.get('nombre','Socio')
    link   = data.get('link','')
    session = Session()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
    session.close()
    if not email:
        return jsonify({'ok': False, 'error': 'Sin email'}), 400
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
      <div style="background:#FF4500;padding:24px;text-align:center">
        <h2 style="margin:0;color:white;font-size:20px">🏋️ {gym_nombre}</h2>
        <p style="margin:6px 0 0;color:#fff9;font-size:13px">Tu app personal</p>
      </div>
      <div style="padding:24px">
        <p style="font-size:15px">Hola <strong>{nombre.split()[0]}</strong>!</p>
        <p style="color:#aaa;font-size:13px;margin-top:8px">Ya tenés acceso a tu app personal de {gym_nombre}. Desde ahí podés ver tu membresía, tu QR de acceso, tus pagos, tu plan de alimentación y tu rutina de entrenamiento.</p>
        <div style="text-align:center;margin:24px 0">
          <a href="{link}" style="background:#FF4500;color:white;text-decoration:none;padding:14px 32px;border-radius:12px;font-size:15px;font-weight:600;display:inline-block">Abrir mi app 📱</a>
        </div>
        <p style="color:#555;font-size:11px;text-align:center">Desde tu celular, abrí el link y tocá "Agregar a pantalla de inicio" para instalarlo como una app.</p>
        <p style="color:#555;font-size:11px;text-align:center;margin-top:4px">Link: {link}</p>
      </div>
    </div>"""
    try:
        session2 = Session()
        enviar_email(email, f'Tu app de {gym_nombre} 📱', html, session2)
        session2.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── RENOVACION PWA ───────────────────────────────────────
@app.route('/api/socio/<int:sid>/renovacion', methods=['POST'])
def solicitar_renovacion(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
    gym_email  = cfg.get('gym_email', '')
    if not gym_email:
        session.close(); return jsonify({'ok': False, 'error': 'El gimnasio no tiene email configurado'}), 400
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
      <div style="background:#FF4500;padding:24px;text-align:center">
        <h2 style="margin:0;color:white">🏋️ {gym_nombre}</h2>
        <p style="margin:6px 0 0;color:#fff9;font-size:13px">Solicitud de renovación</p>
      </div>
      <div style="padding:24px">
        <p style="font-size:15px">El socio <strong>{s.nombre}</strong> quiere renovar su membresía.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="border-bottom:1px solid #333"><td style="padding:8px 0;color:#888;font-size:12px">Plan actual</td><td style="text-align:right;font-size:13px">{s.plan or '—'}</td></tr>
          <tr style="border-bottom:1px solid #333"><td style="padding:8px 0;color:#888;font-size:12px">Vencimiento</td><td style="text-align:right;font-size:13px;color:#FF4444">{str(s.fecha_venc) if s.fecha_venc else '—'}</td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:12px">Teléfono</td><td style="text-align:right;font-size:13px">{s.telefono or '—'}</td></tr>
        </table>
        <p style="color:#666;font-size:12px">Contactate con el socio para coordinar el pago.</p>
      </div>
    </div>"""
    try:
        enviar_email(gym_email, f'Solicitud de renovación — {s.nombre}', html, session)
        session.close()
        return jsonify({'ok': True})
    except Exception as e:
        session.close()
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── EMAIL VENCIMIENTO ────────────────────────────────────
@app.route('/api/socios/<int:sid>/email_vencimiento', methods=['POST'])
def email_vencimiento(sid):
    session = Session()
    socio = session.query(Socio).get(sid)
    if not socio:
        session.close(); return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    if not socio.email:
        session.close(); return jsonify({'ok': False, 'error': 'El socio no tiene email registrado'}), 400
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
    gym_tel    = cfg.get('gym_telefono', '')
    venc = str(socio.fecha_venc) if socio.fecha_venc else '—'
    hoy  = date.today()
    dias = (socio.fecha_venc - hoy).days if socio.fecha_venc else 0
    color_dias = '#FF4444' if dias <= 0 else '#f59e0b' if dias <= 3 else '#FF4500'
    txt_dias   = f'Venció hace {abs(dias)} días' if dias < 0 else ('Vence HOY' if dias == 0 else f'Vence en {dias} días')
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
      <div style="background:#FF4500;padding:24px;text-align:center">
        <h2 style="margin:0;color:white;font-size:20px">🏋️ {gym_nombre}</h2>
        <p style="margin:6px 0 0;color:#fff9;font-size:13px">Aviso de vencimiento</p>
      </div>
      <div style="padding:24px">
        <p style="font-size:15px">Hola <strong>{socio.nombre.split()[0]}</strong>,</p>
        <div style="background:#1a1a1a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center;margin:16px 0">
          <div style="font-size:13px;color:#888;margin-bottom:6px">Estado de tu membresía</div>
          <div style="font-size:22px;font-weight:bold;color:{color_dias}">{txt_dias}</div>
          <div style="font-size:12px;color:#666;margin-top:4px">Vencimiento: {venc}</div>
        </div>
        <p style="color:#aaa;font-size:13px">Para renovar tu membresía y seguir entrenando, comunicate con nosotros:</p>
        {'<p style="font-size:14px">📞 ' + gym_tel + '</p>' if gym_tel else ''}
        <p style="color:#666;font-size:11px;margin-top:20px;text-align:center">¡Te esperamos! 💪</p>
      </div>
    </div>"""
    try:
        enviar_email(socio.email, f'Tu membresía en {gym_nombre} — {txt_dias}', html, session)
        session.close()
        return jsonify({'ok': True, 'mensaje': f'Aviso enviado a {socio.email}'})
    except Exception as e:
        session.close()
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── INGRESOS ─────────────────────────────────────────────
@app.route('/api/ingresos', methods=['POST'])
def registrar_ingreso():
    session = Session()
    ingreso = Ingreso(socio_id=request.json['socio_id'])
    session.add(ingreso); session.commit(); session.close()
    return jsonify({'ok': True})

@app.route('/api/ingresos/hoy', methods=['GET'])
def ingresos_hoy():
    session = Session()
    hoy     = date.today()
    ingresos = session.query(Ingreso).filter(Ingreso.fecha == hoy).order_by(Ingreso.hora.desc()).all()
    result  = []
    for i in ingresos:
        s = session.query(Socio).get(i.socio_id)
        result.append({'socio_id':i.socio_id,'nombre':s.nombre if s else 'Desconocido',
                       'hora':i.hora.strftime('%H:%M') if i.hora else '','foto':s.foto if s else None})
    session.close(); return jsonify(result)

# ── CLASES ───────────────────────────────────────────────
@app.route('/api/clases', methods=['GET'])
def get_clases():
    session = Session()
    dia = request.args.get('dia')
    q   = session.query(Clase)
    if dia: q = q.filter(Clase.dia == dia)
    result = [{'id':c.id,'nombre':c.nombre,'profesor':c.profesor,'dia':c.dia,
               'hora':c.hora,'cupo_max':c.cupo_max,'cupo_act':c.cupo_act} for c in q.all()]
    session.close(); return jsonify(result)

@app.route('/api/clases', methods=['POST'])
def crear_clase():
    session = Session()
    data    = request.json
    clase   = Clase(nombre=data['nombre'],profesor=data.get('profesor',''),
                    dia=data.get('dia',''),hora=data.get('hora',''),cupo_max=data.get('cupo_max',20))
    session.add(clase); session.commit(); session.close()
    return jsonify({'ok': True}), 201

# ── VENCIMIENTOS ─────────────────────────────────────────
@app.route('/api/vencimientos', methods=['GET'])
def get_vencimientos():
    session = Session()
    hoy = date.today()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    dias_alerta = int(cfg.get('dias_alerta_vencimiento', 7))
    socios = session.query(Socio).filter_by(activo=1, congelado=0).all()
    result = []
    for s in socios:
        if not s.fecha_venc: continue
        dias = (s.fecha_venc - hoy).days
        if -30 <= dias <= dias_alerta:  # incluye vencidos recientes
            result.append({
                'id': s.id,
                'nombre': s.nombre,
                'telefono': s.telefono or '',
                'plan': s.plan or '',
                'fecha_venc': str(s.fecha_venc),
                'dias_restantes': dias,
                'estado': 'vencido' if dias < 0 else 'por_vencer'
            })
    result.sort(key=lambda x: x['dias'])
    session.close()
    return jsonify({'socios': result, 'dias_alerta': dias_alerta})

# ── REPORTES ─────────────────────────────────────────────
@app.route('/api/reportes', methods=['GET'])
def get_reportes():
    from datetime import timedelta
    session = Session()
    hoy     = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes    = hoy.replace(day=1)

    # Socios
    socios_activos = session.query(Socio).filter_by(activo=1).all()
    total    = len(socios_activos)
    al_dia   = sum(1 for s in socios_activos if s.fecha_venc and s.fecha_venc >= hoy)
    morosos  = total - al_dia
    vencen_pronto = sum(1 for s in socios_activos
                        if s.fecha_venc and 0 <= (s.fecha_venc - hoy).days <= 7)

    # Ingresos físicos
    ingresos_hoy = session.query(Ingreso).filter(Ingreso.fecha == hoy).count()

    # Pagos — dinero
    pagos_hoy    = session.query(Pago).filter(Pago.fecha == hoy).all()
    pagos_semana = session.query(Pago).filter(Pago.fecha >= inicio_semana).all()
    pagos_mes    = session.query(Pago).filter(Pago.fecha >= inicio_mes).all()

    recaudado_hoy    = sum(p.monto for p in pagos_hoy)
    recaudado_semana = sum(p.monto for p in pagos_semana)
    recaudado_mes    = sum(p.monto for p in pagos_mes)

    # Métodos de pago del mes
    metodos = {}
    for p in pagos_mes:
        m = p.metodo or 'efectivo'
        metodos[m] = metodos.get(m, 0) + p.monto

    # Últimos 7 días de recaudación
    ultimos7 = []
    for i in range(6, -1, -1):
        d = hoy - timedelta(days=i)
        total_dia = sum(p.monto for p in session.query(Pago).filter(Pago.fecha == d).all())
        ultimos7.append({'fecha': str(d), 'dia': d.strftime('%a'), 'monto': total_dia})

    # Planes más vendidos este mes
    planes = {}
    for p in pagos_mes:
        pl = p.plan or 'Sin plan'
        planes[pl] = planes.get(pl, 0) + 1

    session.close()
    return jsonify({
        'total_socios': total,
        'al_dia': al_dia,
        'morosos': morosos,
        'vencen_pronto': vencen_pronto,
        'ingresos_hoy': ingresos_hoy,
        'recaudado_hoy': recaudado_hoy,
        'recaudado_semana': recaudado_semana,
        'recaudado_mes': recaudado_mes,
        'metodos': metodos,
        'ultimos7': ultimos7,
        'planes': planes,
        'cantidad_pagos_hoy': len(pagos_hoy),
        'cantidad_pagos_mes': len(pagos_mes),
    })

# ── CONFIG ───────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
def get_config():
    session = Session()
    result  = {c.clave: c.valor for c in session.query(Config).all()}
    session.close(); return jsonify(result)

@app.route('/api/config', methods=['POST'])
def set_config():
    session = Session()
    for clave, valor in request.json.items():
        c = session.query(Config).filter_by(clave=clave).first()
        if c: c.valor = valor
        else: session.add(Config(clave=clave, valor=valor))
    session.commit(); session.close(); return jsonify({'ok': True})

# ── ARRANCAR ─────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
