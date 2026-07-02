import sys, cv2, requests, json, numpy as np
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QStackedWidget, QFrame, QLineEdit,
    QComboBox, QFormLayout, QScrollArea, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

API = 'http://localhost:5000'

BG='#0d0d0d'; BG2='#111111'; BG3='#1a1a1a'; BORDER='#1e1e1e'
ACCENT='#FF4500'; GREEN='#00FF88'; RED='#FF3333'
TEXT='#ffffff'; TEXT2='#888888'; TEXT3='#555555'

STYLE = f"""
QMainWindow,QWidget{{background:{BG};color:{TEXT};font-family:'Segoe UI'}}
QLabel{{color:{TEXT}}}
QPushButton{{background:{ACCENT};color:white;border:none;border-radius:8px;padding:8px 16px;font-size:13px}}
QPushButton:hover{{background:#e03d00}}
QPushButton#btnSec{{background:{BG3};color:{TEXT2};border:1px solid {BORDER}}}
QPushButton#btnSec:hover{{background:#222;color:white}}
QPushButton#btnVerde{{background:transparent;color:{GREEN};border:1px solid {GREEN};border-radius:8px;padding:6px 14px}}
QLineEdit,QComboBox{{background:{BG2};color:{TEXT};border:1px solid #2a2a2a;border-radius:8px;padding:8px 12px;font-size:13px}}
QLineEdit:focus,QComboBox:focus{{border-color:{ACCENT}}}
QScrollArea{{border:none}}
QScrollBar:vertical{{background:{BG};width:6px}}
QScrollBar::handle:vertical{{background:#333;border-radius:3px}}
"""

# ── HILO CÁMARA + RECONOCIMIENTO FACIAL (mediapipe) ──────
class CamaraThread(QThread):
    frame_signal   = pyqtSignal(QImage)
    socio_signal   = pyqtSignal(dict)
    no_face_signal = pyqtSignal()

    def __init__(self, cam_index=0):
        super().__init__()
        self.cam_index  = cam_index
        self.running    = False
        self.enc_db     = []
        self.ultimo_id  = None
        self.sin_cara   = 0

    def cargar_encodings(self):
        try:
            r = requests.get(f'{API}/api/encodings', timeout=2)
            self.enc_db = r.json()
        except:
            self.enc_db = []

    def run(self):
        import mediapipe as mp
        self.cargar_encodings()
        mp_face = mp.solutions.face_detection
        detector = mp_face.FaceDetection(min_detection_confidence=0.6)
        cap = cv2.VideoCapture(self.cam_index)
        self.running = True
        fc = 0
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            self.frame_signal.emit(QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888))
            fc += 1
            if fc % 15 != 0:
                continue
            # Detectar cara con mediapipe
            results = detector.process(rgb)
            if not results.detections:
                self.sin_cara += 1
                if self.sin_cara > 10:
                    self.ultimo_id = None
                    self.no_face_signal.emit()
                continue
            self.sin_cara = 0
            # Si hay encodings en DB, comparar
            if self.enc_db:
                # Recortar cara detectada
                det = results.detections[0]
                bb = det.location_data.relative_bounding_box
                x1 = max(0, int(bb.xmin * w))
                y1 = max(0, int(bb.ymin * h))
                x2 = min(w, int((bb.xmin + bb.width) * w))
                y2 = min(h, int((bb.ymin + bb.height) * h))
                cara = cv2.resize(rgb[y1:y2, x1:x2], (128, 128))
                enc_actual = cara.flatten().astype(np.float32)
                enc_actual = enc_actual / (np.linalg.norm(enc_actual) + 1e-6)
                # Comparar contra DB
                mejor_sim = -1
                mejor_id  = None
                for e in self.enc_db:
                    vec = np.array(e['encoding'], dtype=np.float32)
                    vec = vec / (np.linalg.norm(vec) + 1e-6)
                    sim = float(np.dot(enc_actual, vec))
                    if sim > mejor_sim:
                        mejor_sim = sim
                        mejor_id  = e['socio_id']
                if mejor_sim > 0.85 and mejor_id != self.ultimo_id:
                    self.ultimo_id = mejor_id
                    try:
                        r2 = requests.get(f'{API}/api/socios/{mejor_id}', timeout=2)
                        data = r2.json()
                        self.socio_signal.emit(data)
                        if data.get('estado') == 'al_dia':
                            requests.post(f'{API}/api/ingresos', json={'socio_id': mejor_id}, timeout=2)
                    except:
                        pass
            else:
                # Sin DB, igual mostrar que detectó cara
                self.sin_cara = 0
        cap.release()
        detector.close()

    def stop(self):
        self.running = False
        self.wait()

# ── WIDGET CÁMARA ────────────────────────────────────────
class CamaraWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f'background:#000;color:{TEXT3};')
        self.setText('Cámara no iniciada')
        self.setMinimumSize(640, 460)
        self.thread = None

    def iniciar(self, idx=0):
        if self.thread:
            self.thread.stop()
        self.thread = CamaraThread(idx)
        self.thread.frame_signal.connect(self.mostrar_frame)
        self.thread.start()
        return self.thread

    def detener(self):
        if self.thread:
            self.thread.stop()
            self.thread = None
        self.setText('Cámara detenida')

    def mostrar_frame(self, img):
        pix = QPixmap.fromImage(img).scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(pix)

# ── PANTALLA INGRESO ─────────────────────────────────────
class PantallaIngreso(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        cam_area = QWidget()
        cam_area.setStyleSheet('background:#000;')
        cl = QVBoxLayout(cam_area)
        self.camWidget = CamaraWidget()
        cl.addWidget(self.camWidget)
        br = QHBoxLayout()
        self.btnCam = QPushButton('▶  Iniciar cámara')
        self.btnCam.clicked.connect(self.toggle_cam)
        br.addStretch(); br.addWidget(self.btnCam)
        cl.addLayout(br)
        layout.addWidget(cam_area)
        panel = QFrame()
        panel.setFixedWidth(270)
        panel.setStyleSheet(f'background:{BG2};border-left:1px solid {BORDER};')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14,14,14,14)
        pl.setSpacing(8)
        t = QLabel('ESTADO DEL SOCIO')
        t.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:2px;')
        pl.addWidget(t)
        self.lblNombre = QLabel('Esperando...')
        self.lblNombre.setStyleSheet(f'color:{TEXT};font-size:15px;font-weight:600;')
        pl.addWidget(self.lblNombre)
        self.lblPlan = QLabel('Sin escanear')
        self.lblPlan.setStyleSheet(f'color:{TEXT3};font-size:11px;')
        pl.addWidget(self.lblPlan)
        self.lblEstado = QLabel('⏳  En espera')
        self.lblEstado.setStyleSheet(f'color:{TEXT3};font-size:12px;background:{BG3};border-radius:10px;padding:4px 12px;')
        self.lblEstado.setFixedWidth(160)
        pl.addWidget(self.lblEstado)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color:{BORDER};'); pl.addWidget(sep)
        self.lblVenc   = self._fila(pl, 'Vencimiento')
        self.lblDias   = self._fila(pl, 'Días restantes')
        self.lblUltimo = self._fila(pl, 'Último ingreso')
        pl.addStretch()
        lh = QLabel('ÚLTIMOS INGRESOS')
        lh.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:2px;')
        pl.addWidget(lh)
        self.histWidget = QWidget()
        self.histLayout = QVBoxLayout(self.histWidget)
        self.histLayout.setContentsMargins(0,0,0,0)
        self.histLayout.setSpacing(4)
        pl.addWidget(self.histWidget)
        layout.addWidget(panel)
        self.cam_activa = False
        self.cam_thread = None
        self.cargar_historial()

    def _fila(self, parent, label):
        row = QHBoxLayout()
        l = QLabel(label); l.setStyleSheet(f'color:{TEXT3};font-size:11px;')
        v = QLabel('--'); v.setStyleSheet(f'color:{TEXT2};font-size:11px;')
        v.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(l); row.addWidget(v)
        parent.addLayout(row)
        return v

    def toggle_cam(self):
        if not self.cam_activa:
            self.cam_thread = self.camWidget.iniciar(0)
            self.cam_thread.socio_signal.connect(self.mostrar_socio)
            self.cam_thread.no_face_signal.connect(self.reset_panel)
            self.btnCam.setText('⏹  Detener cámara')
            self.cam_activa = True
        else:
            self.camWidget.detener()
            self.btnCam.setText('▶  Iniciar cámara')
            self.cam_activa = False
            self.reset_panel()

    def mostrar_socio(self, s):
        ok = s.get('estado') == 'al_dia'
        self.lblNombre.setText(s.get('nombre','--'))
        self.lblPlan.setText(f"{s.get('plan','--')} · #{str(s.get('id',0)).zfill(4)}")
        if ok:
            self.lblEstado.setText('✅  Acceso permitido')
            self.lblEstado.setStyleSheet(f'color:{GREEN};font-size:12px;background:#00FF8815;border-radius:10px;padding:4px 12px;')
            self.lblDias.setStyleSheet(f'color:{GREEN};font-size:11px;')
        else:
            self.lblEstado.setText('❌  Cuota vencida')
            self.lblEstado.setStyleSheet(f'color:{RED};font-size:12px;background:#FF333315;border-radius:10px;padding:4px 12px;')
            self.lblDias.setStyleSheet(f'color:{RED};font-size:11px;')
        self.lblVenc.setText(s.get('fecha_venc','--') or '--')
        dias = s.get('dias_restantes')
        if dias is not None:
            self.lblDias.setText(f'{dias} días' if dias >= 0 else f'Vencido hace {abs(dias)} días')
        self.cargar_historial()

    def reset_panel(self):
        self.lblNombre.setText('Esperando...')
        self.lblPlan.setText('Sin escanear')
        self.lblEstado.setText('⏳  En espera')
        self.lblEstado.setStyleSheet(f'color:{TEXT3};font-size:12px;background:{BG3};border-radius:10px;padding:4px 12px;')
        self.lblVenc.setText('--')
        self.lblDias.setText('--')
        self.lblDias.setStyleSheet(f'color:{TEXT2};font-size:11px;')

    def cargar_historial(self):
        try:
            r = requests.get(f'{API}/api/ingresos/hoy', timeout=2)
            data = r.json()
            for i in reversed(range(self.histLayout.count())):
                w = self.histLayout.itemAt(i).widget()
                if w: w.deleteLater()
            for item in data[:6]:
                w = QWidget()
                rl = QHBoxLayout(w); rl.setContentsMargins(0,0,0,0)
                dot = QLabel('●'); dot.setStyleSheet(f'color:{GREEN};font-size:8px;')
                n = QLabel(item['nombre']); n.setStyleSheet(f'color:{TEXT2};font-size:12px;')
                h = QLabel(item['hora']); h.setStyleSheet(f'color:{TEXT3};font-size:11px;')
                rl.addWidget(dot); rl.addWidget(n); rl.addStretch(); rl.addWidget(h)
                self.histLayout.addWidget(w)
        except:
            pass

# ── PANTALLA SOCIOS ──────────────────────────────────────
class PantallaSocios(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        layout = QVBoxLayout(self); layout.setContentsMargins(20,14,20,14)
        header = QHBoxLayout()
        titulo = QLabel('Socios'); titulo.setStyleSheet('font-size:16px;font-weight:600;')
        self.searchInput = QLineEdit(); self.searchInput.setPlaceholderText('Buscar socio...'); self.searchInput.setFixedWidth(200)
        self.searchInput.textChanged.connect(self.cargar)
        btnNuevo = QPushButton('+ Nuevo'); btnNuevo.clicked.connect(lambda: self.main.ir_a('nuevo'))
        header.addWidget(titulo); header.addStretch(); header.addWidget(self.searchInput); header.addWidget(btnNuevo)
        layout.addLayout(header)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.lista = QVBoxLayout(self.container); self.lista.setAlignment(Qt.AlignmentFlag.AlignTop); self.lista.setSpacing(6)
        scroll.setWidget(self.container); layout.addWidget(scroll)
        self.cargar()

    def cargar(self):
        q = self.searchInput.text()
        for i in reversed(range(self.lista.count())):
            item = self.lista.itemAt(i)
            if item and item.widget(): item.widget().deleteLater()
        try:
            r = requests.get(f'{API}/api/socios?q={q}', timeout=2)
            socios = r.json()
            if not socios:
                lbl = QLabel('No se encontraron socios'); lbl.setStyleSheet(f'color:{TEXT3};padding:20px;')
                self.lista.addWidget(lbl); return
            for s in socios:
                ok = s['estado'] == 'al_dia'
                row = QFrame(); row.setStyleSheet(f'background:{BG2};border:1px solid {BORDER};border-radius:10px;')
                rl = QHBoxLayout(row)
                dot = QLabel('●'); dot.setStyleSheet(f'color:{GREEN if ok else RED};font-size:12px;')
                info = QVBoxLayout()
                n = QLabel(s['nombre']); n.setStyleSheet(f'color:{TEXT};font-size:13px;font-weight:500;')
                sub = QLabel(f"{s.get('plan','Sin plan')} · #{str(s['id']).zfill(4)}"); sub.setStyleSheet(f'color:{TEXT3};font-size:11px;')
                info.addWidget(n); info.addWidget(sub)
                est = QLabel('Al día' if ok else 'Vencido'); est.setStyleSheet(f'color:{GREEN if ok else RED};font-size:11px;')
                est.setAlignment(Qt.AlignmentFlag.AlignRight)
                rl.addWidget(dot); rl.addLayout(info); rl.addStretch(); rl.addWidget(est)
                self.lista.addWidget(row)
        except:
            lbl = QLabel('Error al conectar'); lbl.setStyleSheet(f'color:{RED};padding:20px;')
            self.lista.addWidget(lbl)

# ── PANTALLA NUEVO SOCIO ─────────────────────────────────
class PantallaNuevo(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.foto_base64 = None
        self.cam_thread = None
        self.frame_actual = None
        layout = QVBoxLayout(self); layout.setContentsMargins(20,14,20,14)
        titulo = QLabel('Nuevo socio'); titulo.setStyleSheet('font-size:16px;font-weight:600;')
        layout.addWidget(titulo)
        form_area = QHBoxLayout()
        form = QFormLayout(); form.setSpacing(12)
        self.fNombre = QLineEdit(); self.fNombre.setPlaceholderText('Ej: Carlos Mendoza')
        self.fDni    = QLineEdit(); self.fDni.setPlaceholderText('Ej: 30.123.456')
        self.fTel    = QLineEdit(); self.fTel.setPlaceholderText('Ej: 264 512-3456')
        self.fEmail  = QLineEdit(); self.fEmail.setPlaceholderText('Ej: carlos@email.com')
        self.fPlan   = QComboBox(); self.fPlan.addItems(['Plan Mensual','Plan Trimestral','Plan Anual'])
        ls = f'color:{TEXT2};font-size:11px;'
        for lbl, w in [('Nombre *',self.fNombre),('DNI',self.fDni),('Teléfono',self.fTel),('Email',self.fEmail),('Plan',self.fPlan)]:
            l = QLabel(lbl); l.setStyleSheet(ls); form.addRow(l, w)
        lw = QWidget(); lw.setLayout(form); form_area.addWidget(lw)
        right = QVBoxLayout()
        lf = QLabel('Foto para reconocimiento facial'); lf.setStyleSheet(f'color:{TEXT2};font-size:11px;')
        right.addWidget(lf)
        self.camCaptura = QLabel('Sin foto')
        self.camCaptura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camCaptura.setFixedSize(280,200)
        self.camCaptura.setStyleSheet(f'background:#000;border:1px dashed #2a2a2a;border-radius:10px;color:{TEXT3};')
        right.addWidget(self.camCaptura)
        btns = QHBoxLayout()
        self.btnAbrir = QPushButton('📷 Abrir cámara'); self.btnAbrir.clicked.connect(self.abrir_camara)
        self.btnCapt  = QPushButton('✅ Capturar'); self.btnCapt.setEnabled(False); self.btnCapt.clicked.connect(self.capturar)
        btns.addWidget(self.btnAbrir); btns.addWidget(self.btnCapt)
        right.addLayout(btns); right.addStretch()
        rw = QWidget(); rw.setLayout(right); form_area.addWidget(rw)
        layout.addLayout(form_area)
        footer = QHBoxLayout(); footer.addStretch()
        btnCancel = QPushButton('Cancelar'); btnCancel.setObjectName('btnSec'); btnCancel.clicked.connect(lambda: self.main.ir_a('socios'))
        btnSave   = QPushButton('✓ Guardar socio'); btnSave.clicked.connect(self.guardar)
        footer.addWidget(btnCancel); footer.addWidget(btnSave)
        layout.addLayout(footer)

    def abrir_camara(self):
        # Usar hilo simple sin facial para captura
        class SimpleCam(QThread):
            frame_signal = pyqtSignal(QImage)
            def __init__(self): super().__init__(); self.running=False
            def run(self):
                cap = cv2.VideoCapture(0); self.running=True
                while self.running:
                    ret,frame=cap.read()
                    if ret:
                        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                        h,w,ch=rgb.shape
                        self.frame_signal.emit(QImage(rgb.data,w,h,ch*w,QImage.Format.Format_RGB888))
                cap.release()
            def stop(self): self.running=False; self.wait()
        if self.cam_thread: self.cam_thread.stop()
        self.cam_thread = SimpleCam()
        self.cam_thread.frame_signal.connect(self.mostrar_frame)
        self.cam_thread.start()
        self.btnCapt.setEnabled(True)
        self.btnAbrir.setText('🔄 Repetir')

    def mostrar_frame(self, img):
        self.frame_actual = img
        pix = QPixmap.fromImage(img).scaled(280,200,Qt.AspectRatioMode.KeepAspectRatio)
        self.camCaptura.setPixmap(pix)

    def capturar(self):
        if not self.frame_actual: return
        import base64, tempfile, os
        pix = QPixmap.fromImage(self.frame_actual)
        tmp = tempfile.mktemp(suffix='.jpg')
        pix.save(tmp, 'JPEG')
        with open(tmp,'rb') as f:
            self.foto_base64 = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
        os.unlink(tmp)
        self.camCaptura.setPixmap(pix.scaled(280,200,Qt.AspectRatioMode.KeepAspectRatio))
        if self.cam_thread: self.cam_thread.stop()
        self.btnCapt.setEnabled(False)
        self.btnAbrir.setText('📷 Repetir')

    def guardar(self):
        nombre = self.fNombre.text().strip()
        if not nombre:
            QMessageBox.warning(self,'Error','El nombre es obligatorio'); return
        body = {'nombre':nombre,'dni':self.fDni.text(),'telefono':self.fTel.text(),
                'email':self.fEmail.text(),'plan':self.fPlan.currentText(),
                'fecha_inicio':str(date.today()),'foto_base64':self.foto_base64}
        try:
            r = requests.post(f'{API}/api/socios', json=body, timeout=10)
            if r.status_code == 201:
                QMessageBox.information(self,'GymOS','Socio guardado ✅')
                for f in [self.fNombre,self.fDni,self.fTel,self.fEmail]: f.clear()
                self.foto_base64 = None
                self.camCaptura.setText('Sin foto')
                self.main.ir_a('socios')
            else:
                QMessageBox.warning(self,'Error','No se pudo guardar el socio')
        except Exception as e:
            QMessageBox.warning(self,'Error',f'No se pudo conectar: {e}')

# ── PANTALLA CUOTAS ──────────────────────────────────────
class PantallaCuotas(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(20,14,20,14)
        titulo = QLabel('Cuotas y pagos'); titulo.setStyleSheet('font-size:16px;font-weight:600;')
        layout.addWidget(titulo)
        self.statsRow = QHBoxLayout()
        self.cAlDia   = self._card('--','Al día',GREEN)
        self.cMorosos = self._card('--','Morosos',RED)
        self.cTotal   = self._card('--','Total',TEXT)
        layout.addLayout(self.statsRow)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.lista = QVBoxLayout(self.container); self.lista.setAlignment(Qt.AlignmentFlag.AlignTop); self.lista.setSpacing(6)
        scroll.setWidget(self.container); layout.addWidget(scroll)
        self.cargar()

    def _card(self,val,lbl,color):
        card=QFrame(); card.setStyleSheet(f'background:{BG2};border:1px solid {BORDER};border-radius:10px;')
        cl=QVBoxLayout(card)
        v=QLabel(val); v.setStyleSheet(f'color:{color};font-size:26px;font-weight:600;')
        l=QLabel(lbl); l.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:1px;')
        cl.addWidget(v); cl.addWidget(l); self.statsRow.addWidget(card); return v

    def cargar(self):
        for i in reversed(range(self.lista.count())):
            item=self.lista.itemAt(i)
            if item and item.widget(): item.widget().deleteLater()
        try:
            r=requests.get(f'{API}/api/socios',timeout=2); socios=r.json()
            morosos=[s for s in socios if s['estado']!='al_dia']
            al_dia=[s for s in socios if s['estado']=='al_dia']
            self.cAlDia.setText(str(len(al_dia))); self.cMorosos.setText(str(len(morosos))); self.cTotal.setText(str(len(socios)))
            if morosos:
                sec=QLabel('MOROSOS'); sec.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:2px;margin-top:8px;')
                self.lista.addWidget(sec)
                for s in morosos: self.lista.addWidget(self._item(s))
            sec2=QLabel('AL DÍA'); sec2.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:2px;margin-top:8px;')
            self.lista.addWidget(sec2)
            for s in al_dia: self.lista.addWidget(self._item(s))
        except: pass

    def _item(self,s):
        ok=s['estado']=='al_dia'
        row=QFrame(); row.setStyleSheet(f'background:{BG2};border:1px solid {BORDER};border-radius:10px;')
        rl=QHBoxLayout(row)
        dot=QLabel('●'); dot.setStyleSheet(f'color:{GREEN if ok else RED};font-size:12px;')
        info=QVBoxLayout()
        n=QLabel(s['nombre']); n.setStyleSheet(f'color:{TEXT};font-size:13px;font-weight:500;')
        sub=QLabel(f"{'Vence' if ok else 'Venció'} {s.get('fecha_venc','--')} · {s.get('plan','')}"); sub.setStyleSheet(f'color:{TEXT3};font-size:11px;')
        info.addWidget(n); info.addWidget(sub)
        btn=QPushButton('Registrar pago'); btn.setObjectName('btnVerde')
        btn.clicked.connect(lambda _,sid=s['id'],sn=s['nombre'],sp=s.get('plan',''): self.pagar(sid,sn,sp))
        rl.addWidget(dot); rl.addLayout(info); rl.addStretch(); rl.addWidget(btn); return row

    def pagar(self,sid,nombre,plan):
        precios={'Plan Mensual':18000,'Plan Trimestral':50000,'Plan Anual':180000}
        monto=precios.get(plan,18000)
        reply=QMessageBox.question(self,'Registrar pago',f'¿Registrar pago de ${monto:,} para {nombre}?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if reply==QMessageBox.StandardButton.Yes:
            try:
                r=requests.post(f'{API}/api/pagos',json={'socio_id':sid,'monto':monto,'metodo':'efectivo'},timeout=5)
                if r.ok: QMessageBox.information(self,'GymOS','Pago registrado ✅'); self.cargar()
            except: QMessageBox.warning(self,'Error','No se pudo registrar')

# ── PANTALLA REPORTES ────────────────────────────────────
class PantallaReportes(QWidget):
    def __init__(self):
        super().__init__()
        layout=QVBoxLayout(self); layout.setContentsMargins(20,14,20,14)
        titulo=QLabel('Reportes'); titulo.setStyleSheet('font-size:16px;font-weight:600;')
        layout.addWidget(titulo)
        stats=QHBoxLayout(); self.cards={}
        for key,lbl,color in [('total_socios','Socios activos',TEXT),('ingresos_hoy','Ingresos hoy',TEXT),('al_dia','Al día',GREEN),('morosos','Morosos',RED)]:
            card=QFrame(); card.setStyleSheet(f'background:{BG2};border:1px solid {BORDER};border-radius:10px;')
            cl=QVBoxLayout(card)
            v=QLabel('--'); v.setStyleSheet(f'color:{color};font-size:28px;font-weight:600;')
            l=QLabel(lbl); l.setStyleSheet(f'color:{TEXT3};font-size:10px;letter-spacing:1px;')
            cl.addWidget(v); cl.addWidget(l); stats.addWidget(card); self.cards[key]=v
        layout.addLayout(stats); layout.addStretch(); self.cargar()

    def cargar(self):
        try:
            r=requests.get(f'{API}/api/reportes',timeout=2); d=r.json()
            for key,v in self.cards.items(): v.setText(str(d.get(key,'--')))
        except: pass

# ── PANTALLA CONFIG ──────────────────────────────────────
class PantallaConfig(QWidget):
    def __init__(self,main_window):
        super().__init__()
        self.main=main_window
        layout=QVBoxLayout(self); layout.setContentsMargins(20,14,20,14)
        header=QHBoxLayout()
        titulo=QLabel('Configuración'); titulo.setStyleSheet('font-size:16px;font-weight:600;')
        btnG=QPushButton('✓ Guardar'); btnG.clicked.connect(self.guardar)
        header.addWidget(titulo); header.addStretch(); header.addWidget(btnG)
        layout.addLayout(header)
        form=QFormLayout(); form.setSpacing(12)
        self.cfgNombre=QLineEdit(); self.cfgTel=QLineEdit()
        self.cfgMensual=QLineEdit(); self.cfgTrimestral=QLineEdit(); self.cfgAnual=QLineEdit()
        ls=f'color:{TEXT2};font-size:12px;'
        for lbl,w in [('Nombre del gimnasio',self.cfgNombre),('Teléfono',self.cfgTel),
                      ('Plan Mensual ($)',self.cfgMensual),('Plan Trimestral ($)',self.cfgTrimestral),('Plan Anual ($)',self.cfgAnual)]:
            l=QLabel(lbl); l.setStyleSheet(ls); form.addRow(l,w)
        layout.addLayout(form); layout.addStretch(); self.cargar()

    def cargar(self):
        try:
            r=requests.get(f'{API}/api/config',timeout=2); d=r.json()
            self.cfgNombre.setText(d.get('gym_nombre','')); self.cfgTel.setText(d.get('gym_telefono',''))
            self.cfgMensual.setText(d.get('precio_mensual','')); self.cfgTrimestral.setText(d.get('precio_trimestral','')); self.cfgAnual.setText(d.get('precio_anual',''))
        except: pass

    def guardar(self):
        body={'gym_nombre':self.cfgNombre.text(),'gym_telefono':self.cfgTel.text(),
              'precio_mensual':self.cfgMensual.text(),'precio_trimestral':self.cfgTrimestral.text(),'precio_anual':self.cfgAnual.text()}
        try:
            r=requests.post(f'{API}/api/config',json=body,timeout=5)
            if r.ok:
                self.main.lblGym.setText(body['gym_nombre'])
                QMessageBox.information(self,'GymOS','Configuración guardada ✅')
        except: QMessageBox.warning(self,'Error','No se pudo guardar')

# ── VENTANA PRINCIPAL ────────────────────────────────────
class GymOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GymOS'); self.setMinimumSize(1100,680); self.setStyleSheet(STYLE)
        central=QWidget(); self.setCentralWidget(central)
        ml=QVBoxLayout(central); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        topbar=QFrame(); topbar.setFixedHeight(46)
        topbar.setStyleSheet(f'background:{BG2};border-bottom:1px solid {BORDER};')
        tl=QHBoxLayout(topbar); tl.setContentsMargins(16,0,16,0)
        icon=QLabel('🏋'); icon.setStyleSheet(f'background:{ACCENT};border-radius:6px;padding:4px 8px;font-size:14px;')
        lt=QLabel('GymOS'); lt.setStyleSheet('font-size:15px;font-weight:600;letter-spacing:1px;')
        ls=QLabel('Control de acceso'); ls.setStyleSheet(f'color:{TEXT3};font-size:10px;')
        self.lblGym=QLabel('Mi Gimnasio')
        self.lblGym.setStyleSheet(f'color:{ACCENT};background:#FF450015;border:1px solid #FF450040;border-radius:12px;padding:3px 12px;font-size:11px;')
        self.lblClock=QLabel('--:--:--'); self.lblClock.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        timer=QTimer(self); timer.timeout.connect(self.tick); timer.start(1000); self.tick()
        tl.addWidget(icon); tl.addWidget(lt); tl.addWidget(ls); tl.addStretch(); tl.addWidget(self.lblGym); tl.addWidget(self.lblClock)
        ml.addWidget(topbar)
        body=QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        sidebar=QFrame(); sidebar.setFixedWidth(56)
        sidebar.setStyleSheet(f'background:{BG2};border-right:1px solid {BORDER};')
        sl=QVBoxLayout(sidebar); sl.setContentsMargins(8,10,8,10); sl.setSpacing(2); sl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_btns={}
        for item in [('ingreso','⬡','Ingreso'),('socios','👥','Socios'),('nuevo','➕','Nuevo socio'),
                     None,('cuotas','💰','Cuotas'),('reportes','📊','Reportes'),None,('config','⚙','Config')]:
            if item is None:
                sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f'background:{BORDER};'); sl.addWidget(sep); continue
            key,icon2,tip=item
            btn=QPushButton(icon2); btn.setFixedSize(40,40); btn.setToolTip(tip)
            btn.setStyleSheet(f'background:transparent;color:{TEXT3};border:none;border-radius:8px;font-size:16px;')
            btn.clicked.connect(lambda _,k=key: self.ir_a(k))
            sl.addWidget(btn); self.nav_btns[key]=btn
        body.addWidget(sidebar)
        self.stack=QStackedWidget()
        self.screens={'ingreso':PantallaIngreso(),'socios':PantallaSocios(self),
                      'nuevo':PantallaNuevo(self),'cuotas':PantallaCuotas(),
                      'reportes':PantallaReportes(),'config':PantallaConfig(self)}
        for s in self.screens.values(): self.stack.addWidget(s)
        body.addWidget(self.stack); ml.addLayout(body)
        self.ir_a('ingreso')
        self.cargar_config()

    def ir_a(self,nombre):
        self.stack.setCurrentWidget(self.screens[nombre])
        for key,btn in self.nav_btns.items():
            if key==nombre:
                btn.setStyleSheet(f'background:#FF450020;color:{ACCENT};border:none;border-radius:8px;font-size:16px;')
            else:
                btn.setStyleSheet(f'background:transparent;color:{TEXT3};border:none;border-radius:8px;font-size:16px;')
        if nombre=='socios':   self.screens['socios'].cargar()
        if nombre=='cuotas':   self.screens['cuotas'].cargar()
        if nombre=='reportes': self.screens['reportes'].cargar()

    def tick(self):
        self.lblClock.setText(datetime.now().strftime('%H:%M:%S'))

    def cargar_config(self):
        try:
            r=requests.get(f'{API}/api/config',timeout=2); d=r.json()
            self.lblGym.setText(d.get('gym_nombre','Mi Gimnasio'))
        except: pass

if __name__=='__main__':
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    window=GymOS()
    window.show()
    sys.exit(app.exec())
