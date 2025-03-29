#live
import asyncio
import logging
import sqlite3
import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QMessageBox, QTextEdit, QProgressBar
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from telethon import TelegramClient, events
from telethon.sync import TelegramClient as SyncTelegramClient

from config import api_id, api_hash, SESSION_NAME

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def extract_card_info(message: str) -> str:
    """Extrae información formateada de la tarjeta usando regex."""
    pattern = re.compile(r'(\d{16}\|\d{2}\|\d{4}\|\d{3})')
    match = pattern.search(message)
    return match.group(1) if match else ""

def init_db(db_path='messages.db'):
    """Inicializa la base de datos creando la tabla de mensajes si no existe."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    sender_id INTEGER,
                    chat_info TEXT,
                    message TEXT
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Error inicializando la base de datos: %s", e)

def insert_message(date, sender_id, chat_info, message, db_path='messages.db'):
    """Inserta un mensaje en la base de datos."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (date, sender_id, chat_info, message)
                VALUES (?, ?, ?, ?)
            ''', (date, sender_id, chat_info, message))
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Error insertando mensaje: %s", e)

init_db()

class ExtractionWorker(QThread):
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    new_message_signal = pyqtSignal(str)

    def __init__(self, channel, limit, realtime, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.limit = limit
        self.realtime = realtime

    def process_message(self, msg, chat):
        """Procesa un mensaje extrayendo la información y almacenándola."""
        card_info = extract_card_info(msg.text)
        if card_info:
            # Se usa getattr para obtener 'title' o 'username' de forma segura.
            chat_info = getattr(chat, 'title', None) or getattr(chat, 'username', 'N/A')
            insert_message(str(msg.date), msg.sender_id, chat_info, card_info)
            logger.debug("Processed message: %s", card_info)
            self.new_message_signal.emit(card_info)
            return True
        else:
            logger.debug("Message discarded; no valid pattern.")
            return False

    async def realtime_handler(self, event):
        """Maneja eventos de mensajes en tiempo real."""
        logger.debug("Realtime handler triggered.")
        msg = event.message
        try:
            chat = await event.get_chat()
        except Exception as e:
            logger.exception("Error fetching chat info: %s", e)
            return
        if msg.text:
            if self.process_message(msg, chat):
                self.status_signal.emit("Nuevo mensaje procesado y almacenado.")

    def cancel_loop_tasks(self, loop):
        """Cancela todas las tareas pendientes en el loop de asyncio."""
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.exception("Error canceling tasks: %s", e)

    def run(self):
        """Ejecuta la extracción de mensajes en un hilo separado."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug("ExtractionWorker started. Channel: %s, Limit: %s, Realtime: %s",
                     self.channel, self.limit, self.realtime)
        try:
            self.status_signal.emit("Conectando a Telegram...")
            with SyncTelegramClient(SESSION_NAME, api_id, api_hash) as client:
                logger.debug("Connected to Telegram.")
                if self.realtime:
                    self.status_signal.emit("Modo en tiempo real activado. Esperando mensajes...")
                    client.add_event_handler(self.realtime_handler, events.NewMessage(chats=[self.channel]))
                    logger.debug("Realtime event handler added.")
                    client.run_until_disconnected()
                else:
                    self.status_signal.emit("Extrayendo mensajes...")
                    messages = client.get_messages(self.channel, limit=self.limit)
                    chat = client.get_entity(self.channel)
                    for msg in messages:
                        if msg.text:
                            self.process_message(msg, chat)
                    self.status_signal.emit("Mensajes extraídos y almacenados.")
                    self.finished_signal.emit()
        except Exception as e:
            logger.exception("Error in ExtractionWorker.run: %s", e)
            self.error_signal.emit(str(e))
            self.finished_signal.emit()
        finally:
            logger.debug("Finalizing ExtractionWorker, canceling tasks.")
            self.cancel_loop_tasks(loop)
            loop.close()
            logger.debug("Asyncio loop closed.")

class ModoLiveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self.selected_group = None
        self.init_ui()
        self.setStyleSheet("""
            QWidget {
                background-color: #F8F9FA;
                color: #333333;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #444444;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #FFFFFF;
                border: 2px solid #D1D1D1;
                padding: 6px;
                border-radius: 6px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 2px solid #0078D7;
            }
            QPushButton.groupCard {
                background-color: #FFFFFF;
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
                color: #333333;
            }
            QPushButton.groupCard:hover {
                background-color: #f0f0f0;
            }
            QPushButton.groupCard:checked {
                background-color: #0078D7;
                color: white;
            }
            QPushButton {
                background-color: #0078D7;
                color: white;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: bold;
                transition: all 0.3s ease-in-out;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton#clear_button {
                background-color: #D9534F;
            }
            QPushButton#clear_button:hover {
                background-color: #C9302C;
            }
            QPushButton#cancel_button {
                background-color: #FF9800;
            }
            QPushButton#cancel_button:hover {
                background-color: #F57C00;
            }
            /* Toggle switch estilo para el QCheckBox */
            QCheckBox {
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 50px;
                height: 28px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #d3d3d3;
                border-radius: 14px;
                background-color: #f0f0f0;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078D7;
                border-radius: 14px;
                background-color: #0078D7;
            }
            QProgressBar {
                border: 2px solid #D1D1D1;
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
                background-color: #EAEAEA;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Sección para seleccionar el grupo con "cards"
        group_label = QLabel("Selecciona el grupo:")
        layout.addWidget(group_label)
        self.group_buttons_layout = QHBoxLayout()
        self.group_buttons = []
        groups = ["StripeAuthScrapper", "Lions_scrapperfree", "freedropcards", "Otro"]
        for grp in groups:
            btn = QPushButton(grp)
            btn.setCheckable(True)
            btn.setProperty("class", "groupCard")
            btn.setObjectName("groupCard")
            btn.clicked.connect(self.group_selected)
            self.group_buttons.append(btn)
            self.group_buttons_layout.addWidget(btn)
        layout.addLayout(self.group_buttons_layout)
        
        self.custom_group_input = QLineEdit()
        self.custom_group_input.setPlaceholderText("Ingresa el username del grupo")
        self.custom_group_input.setVisible(False)
        layout.addWidget(self.custom_group_input)
        
        # Sección para el límite de mensajes
        limit_layout = QHBoxLayout()
        limit_label = QLabel("Número de mensajes:")
        self.limit_input = QLineEdit()
        self.limit_input.setText("100")
        limit_layout.addWidget(limit_label)
        limit_layout.addWidget(self.limit_input)
        layout.addLayout(limit_layout)
        
        # Toggle switch para modo realtime
        self.realtime_checkbox = QCheckBox("Modo en tiempo real")
        self.realtime_checkbox.stateChanged.connect(self.update_cancel_button_visibility)
        layout.addWidget(self.realtime_checkbox)
        
        # Botones de acción
        botones_layout = QHBoxLayout()
        self.extract_button = QPushButton("Extraer mensajes")
        self.extract_button.clicked.connect(self.start_extraction)
        botones_layout.addWidget(self.extract_button)
        self.clear_button = QPushButton("LIMPIAR DATOS")
        self.clear_button.setObjectName("clear_button")
        self.clear_button.clicked.connect(self.clear_data)
        botones_layout.addWidget(self.clear_button)
        self.cancel_button = QPushButton("Cancelar Proceso")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.cancel_realtime)
        # El botón de cancelar se muestra siempre
        self.cancel_button.setVisible(True)
        botones_layout.addWidget(self.cancel_button)
        layout.addLayout(botones_layout)
        
        # Barra de carga
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminado
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Área de mensajes y estado
        self.messages_view = QTextEdit()
        self.messages_view.setReadOnly(True)
        layout.addWidget(self.messages_view)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def group_selected(self):
        sender = self.sender()
        for btn in self.group_buttons:
            if btn != sender:
                btn.setChecked(False)
        self.selected_group = sender.text()
        self.custom_group_input.setVisible(self.selected_group == "Otro")

    def update_cancel_button_visibility(self):
        self.cancel_button.setVisible(True)

    def start_extraction(self):
        if not self.selected_group:
            QMessageBox.warning(self, "Error", "Debes seleccionar un grupo.")
            return
        selected_group = (self.custom_group_input.text().strip() 
                          if self.selected_group == "Otro" 
                          else self.selected_group)
        if not selected_group:
            QMessageBox.warning(self, "Error", "Debes ingresar el username del grupo personalizado.")
            return
        try:
            limit = int(self.limit_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "El límite de mensajes debe ser un número entero.")
            return
        realtime = self.realtime_checkbox.isChecked()
        self.status_label.setText(f"Iniciando worker para el grupo {selected_group}...")
        self.progress_bar.setVisible(True)
        logger.debug("ModoLiveWidget.start_extraction: Group: %s, Limit: %d, Realtime: %s",
                     selected_group, limit, realtime)
        worker = ExtractionWorker(selected_group, limit, realtime)
        worker.status_signal.connect(self.update_status)
        worker.error_signal.connect(self.handle_error)
        worker.finished_signal.connect(lambda: self.worker_finished(worker))
        worker.new_message_signal.connect(self.append_message)
        self.workers.append(worker)
        worker.start()

    def worker_finished(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        self.status_label.setText("Un worker finalizó su proceso.")
        logger.debug("Worker finalizado. Workers activos: %d", len(self.workers))
        if not self.workers:
            self.progress_bar.setVisible(False)

    def cancel_realtime(self):
        realtime_workers = [w for w in self.workers if w.realtime]
        if realtime_workers:
            for worker in realtime_workers:
                if worker.isRunning():
                    worker.terminate()
                    worker.wait()
                    self.workers.remove(worker)
            self.status_label.setText("Procesos realtime cancelados.")
            logger.debug("Se cancelaron %d worker(s) realtime.", len(realtime_workers))
        else:
            self.status_label.setText("No hay procesos realtime activos.")
        if not self.workers:
            self.progress_bar.setVisible(False)

    def update_status(self, message):
        self.status_label.setText(message)
        logger.debug("ModoLiveWidget.update_status: %s", message)

    def handle_error(self, error):
        logger.debug("ModoLiveWidget.handle_error: %s", error)
        QMessageBox.critical(self, "Error", f"Ocurrió un error: {error}")

    def append_message(self, message):
        self.messages_view.append(message)
        logger.debug("ModoLiveWidget.append_message: %s", message.strip())

    def clear_data(self):
        self.messages_view.clear()
        self.status_label.setText("Datos limpiados.")
        logger.debug("ModoLiveWidget.clear_data executed: view cleared.")

    def closeEvent(self, event):
        for worker in self.workers:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
        event.accept()
