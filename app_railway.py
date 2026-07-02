from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date, datetime
import os, json, io, smtplib, qrcode
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__, static_folder=None)
CORS(app)

# ── BASE DE DATOS ─────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///gymos.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
FOTOS_DIR = os.path.join(BASE_DIR, 'static', 'fotos')
QR_DIR    = os.path.join(BASE_DIR, 'static', 'qr')
LOGO_DIR  = os.path.join(BASE_DIR, 'static', 'logos')
os.makedirs(FOTOS_DIR, exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(LOGO_DIR, exist_ok=True)

# ── MODELOS ───────────────────────────────────────────────
class Socio(Base):
    __tablename__ = 'socios'
    id           = Column(Integer, primary_key=True)
    nombre       = Column(String(100))
    dni          = Column(String(20))
    telefono     = Column(String(30))
    email        = Column(String(100))
    plan         = Column(String(50))
    objetivo     = Column(String(50))
    fecha_inicio = Column(Date)
    fecha_venc   = Column(Date)
    foto         = Column(String(200))
    activo       = Column(Integer, default=1)
    congelado    = Column(Integer, default=0)
    fecha_congelado = Column(Date)
    dias_congelados = Column(Integer)

class Pago(Base):
    __tablename__ = 'pagos'
    id       = Column(Integer, primary_key=True)
    socio_id = Column(Integer)
    monto    = Column(Integer)
    fecha    = Column(Date, default=date.today)
    metodo   = Column(String(50))
    plan     = Column(String(50))

class Config(Base):
    __tablename__ = 'config'
    id    = Column(Integer, primary_key=True)
    clave = Column(String(100))
    valor = Column(Text)

class FichaMedica(Base):
    __tablename__ = 'fichas_medicas'
    id                   = Column(Integer, primary_key=True)
    socio_id             = Column(Integer, unique=True)
    fecha_nacimiento     = Column(Date)
    sexo                 = Column(String(20))
    grupo_sanguineo      = Column(String(10))
    peso                 = Column(String(10))
    altura               = Column(String(10))
    enfermedades         = Column(Text)
    lesiones             = Column(Text)
    medicacion           = Column(Text)
    alergias             = Column(Text)
    hace_ejercicio       = Column(String(10))
    autorizacion_medica  = Column(String(10))
    observaciones        = Column(Text)
    declaracion_aceptada = Column(Integer, default=0)
    declaracion_fecha    = Column(DateTime)
    declaracion_ip       = Column(String(50))

Base.metadata.create_all(engine)

# ── HELPERS ───────────────────────────────────────────────
def get_cfg():
    session = Session()
    cfg = {c.clave: c.valor for c in session.query(Config).all()}
    session.close()
    return cfg

def enviar_email(destinatario, asunto, html, adjunto_path=None, adjunto_nombre=None):
    cfg = get_cfg()
    gym_email      = cfg.get('gym_email', '')
    gym_email_pass = cfg.get('gym_email_pass', '')
    gym_nombre     = cfg.get('gym_email_nombre') or cfg.get('gym_nombre', 'Gimnasio')
    if not gym_email or not gym_email_pass:
        raise Exception('Email no configurado')
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
        part.add_header('Content-Disposition', f'attachment; filename="{adjunto_nombre or os.path.basename(adjunto_path)}"')
        msg.attach(part)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gym_email, gym_email_pass)
        server.sendmail(gym_email, destinatario, msg.as_string())

# ── RUTAS ESTÁTICAS ───────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'index.html')

@app.route('/socio/<int:sid>')
def pwa_socio(sid):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'socio.html')

@app.route('/ficha/<int:sid>')
def ficha_window(sid):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'ficha.html')

@app.route('/fotos/<path:path>')
def serve_foto(path):
    return send_from_directory(FOTOS_DIR, path)

@app.route('/qr/<path:path>')
def serve_qr(path):
    return send_from_directory(QR_DIR, path)

@app.route('/static/logos/<path:path>')
def serve_logo(path):
    return send_from_directory(LOGO_DIR, path)

# ── API CONFIG ────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(get_cfg())

# ── API PWA SOCIO ─────────────────────────────────────────
@app.route('/api/socio/<int:sid>/pwa', methods=['GET'])
def get_socio_pwa(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    if not s or not s.activo:
        session.close()
        return jsonify({'ok': False, 'error': 'Socio no encontrado'}), 404
    pagos = session.query(Pago).filter_by(socio_id=sid).order_by(Pago.fecha.desc()).limit(5).all()
    cfg = get_cfg()
    hoy = date.today()
    dias = (s.fecha_venc - hoy).days if s.fecha_venc else None
    estado = 'al_dia' if dias and dias >= 0 else 'vencido'
    result = {
        'id': s.id, 'nombre': s.nombre, 'plan': s.plan, 'objetivo': s.objetivo or '',
        'foto': s.foto, 'fecha_venc': str(s.fecha_venc) if s.fecha_venc else None,
        'dias_restantes': dias, 'estado': estado,
        'congelado': s.congelado or 0,
        'fecha_congelado': str(s.fecha_congelado) if s.fecha_congelado else None,
        'dias_congelados': s.dias_congelados,
        'gym_nombre': cfg.get('gym_nombre', 'Gimnasio'),
        'gym_telefono': cfg.get('gym_telefono', ''),
        'gym_email': cfg.get('gym_email', ''),
        'gym_logo': cfg.get('gym_logo', ''),
        'qr_url': f'/qr/socio_{sid}.png',
        'pagos': [{'monto': p.monto, 'fecha': str(p.fecha), 'metodo': p.metodo, 'plan': p.plan} for p in pagos]
    }
    session.close()
    return jsonify({'ok': True, 'socio': result})

@app.route('/api/socios/<int:sid>')
def get_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    session.close()
    if not s: return jsonify({'error': 'No encontrado'}), 404
    return jsonify({'id': s.id, 'nombre': s.nombre, 'email': s.email})

@app.route('/api/socios/<int:sid>/qr', methods=['GET'])
def get_qr_socio(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    session.close()
    if not s: return jsonify({'error': 'No encontrado'}), 404
    qr_filename = f'socio_{sid}.png'
    qr_path = os.path.join(QR_DIR, qr_filename)
    if not os.path.exists(qr_path):
        qr = qrcode.QRCode(version=1, box_size=10, border=4,
                           error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(f'GYMOS:SOCIO:{sid}')
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img.save(qr_path)
    return jsonify({'ok': True, 'qr_url': f'/qr/{qr_filename}', 'socio': s.nombre})

@app.route('/api/socio/<int:sid>/renovacion', methods=['POST'])
def solicitar_renovacion(sid):
    session = Session()
    s = session.query(Socio).get(sid)
    session.close()
    if not s: return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    if not s.email: return jsonify({'ok': False, 'error': 'Sin email'}), 400
    cfg = get_cfg()
    gym_nombre = cfg.get('gym_nombre', 'Gimnasio')
    gym_email  = cfg.get('gym_email', '')
    if not gym_email: return jsonify({'ok': False, 'error': 'Sin email configurado'}), 400
    html = f"""<div style="font-family:Arial;max-width:480px;margin:0 auto;background:#111;color:#eee;border-radius:12px;overflow:hidden">
      <div style="background:#FF4500;padding:24px;text-align:center"><h2 style="margin:0;color:white">🏋️ {gym_nombre}</h2></div>
      <div style="padding:24px"><p>El socio <strong>{s.nombre}</strong> quiere renovar su membresía.</p>
      <p style="color:#aaa">Tel: {s.telefono or '—'} | Vence: {str(s.fecha_venc) if s.fecha_venc else '—'}</p></div></div>"""
    try:
        enviar_email(gym_email, f'Solicitud de renovación — {s.nombre}', html)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
