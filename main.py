#main.py
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtGui import QPalette, QColor, QFont

from sender import MessageSenderWidget
from reader import ModoLectorWidget
from live import ModoLiveWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Utilidad de Telegram - Múltiples Modos")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()

    def init_ui(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Se carga cada widget dentro de bloques try/except para capturar errores y seguir la ejecución
        try:
            self.sender_widget = MessageSenderWidget()
            self.tab_widget.addTab(self.sender_widget, "Envío de Mensajes")
        except Exception as e:
            print("Error al cargar MessageSenderWidget:", e)
        
        try:
            self.lector_widget = ModoLectorWidget()
            self.tab_widget.addTab(self.lector_widget, "Modo Lector")
        except Exception as e:
            print("Error al cargar ModoLectorWidget:", e)
            
        try:
            self.live_widget = ModoLiveWidget()
            self.tab_widget.addTab(self.live_widget, "Modo Live")
        except Exception as e:
            print("Error al cargar ModoLiveWidget:", e)
        
        # Estilos globales aplicados al MainWindow
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLabel { font-size: 14px; color: #333333; }
            QLineEdit, QTextEdit { background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; padding: 4px; font-size: 14px; }
            QPushButton { background-color: #0078d7; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-size: 14px; }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #004578; }
        """)

def create_app():
    """Configura la aplicación, el palette y la fuente global."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(233, 231, 227))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    return app

if __name__ == "__main__":
    try:
        app = create_app()
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print("Error al iniciar la aplicación:", e)
        sys.exit(1)
