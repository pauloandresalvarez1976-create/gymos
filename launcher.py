import threading, sys, os, time, requests

def run_backend():
    from app import app
    app.run(port=5000, debug=False, use_reloader=False)

threading.Thread(target=run_backend, daemon=True).start()

# Esperar hasta que el backend responda
print("Iniciando backend...")
for i in range(20):
    try:
        requests.get('http://localhost:5000/api/config', timeout=1)
        print("Backend listo!")
        break
    except:
        time.sleep(0.5)

from gymos import GymOS
from PyQt6.QtWidgets import QApplication
qt = QApplication(sys.argv)
qt.setStyle('Fusion')
window = GymOS()
window.show()
sys.exit(qt.exec())
