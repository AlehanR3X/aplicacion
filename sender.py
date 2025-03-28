#sender.py
import sys
import asyncio
import logging
import re
from typing import List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QErrorMessage, QComboBox, QSpinBox
)
from PyQt5.QtCore import QThread, pyqtSignal
from telethon import TelegramClient, events

from config import (
    api_id, api_hash, SESSION_NAME, GROUP_CHAT2_ID,
    bot3_user, bot2_username, bot_username, SLEEP_TIME, GROUP_CHAT_ID
)
from data_manager import get_extracted_messages

logger = logging.getLogger(__name__)

def extract_information(message_text: str) -> str:
    """Extrae la información formateada del mensaje utilizando regex."""
    pattern = re.compile(
        r'\b(?:'
        r'(?P<f1>\d{16})\D+(?P<f2>\d{2})\D+(?P<f3>(?:\d{4}|\d{2}))\D+(?P<f4>\d{3})'
        r'|'
        r'(?P<s1>\d{15})\D+(?P<s2>\d{2})\D+(?P<s3>\d{4})\D+(?P<s4>\d{4})'
        r'|'
        r'(?P<t1>\d{15})\D+(?P<t2>\d{2})\D+(?P<t3>\d{2})\D+(?P<t4>\d{4})'
        r')\b'
    )
    for match in pattern.finditer(message_text):
        grupos = match.groupdict()
        if grupos.get("f1"):
            return "|".join([grupos["f1"], grupos["f2"], grupos["f3"], grupos["f4"]])
        elif grupos.get("s1"):
            return "|".join([grupos["s1"], grupos["s2"], grupos["s3"], grupos["s4"]])
        elif grupos.get("t1"):
            return "|".join([grupos["t1"], grupos["t2"], grupos["t3"], grupos["t4"]])
    return "<Patrón no encontrado>"

def format_bot_message(message: str) -> str:
    """Formatea la respuesta del bot resaltando claves y valores."""
    lines = message.splitlines()
    formatted_lines = []
    for line in lines:
        if " -» " in line:
            parts = line.split(" -» ")
            key = parts[0].strip()
            value = " -» ".join(parts[1:]).strip()
            formatted_lines.append(f"<b>{key}:</b> {value}")
        else:
            formatted_lines.append(line)
    return "<br>".join(formatted_lines)

class MessageSenderThread(QThread):
    update_history = pyqtSignal(str)
    update_data = pyqtSignal(list)
    finished_sending = pyqtSignal()

    def __init__(self, prefix: str, lines: List[str], destination: str, sleep_time: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.prefix = prefix
        self.lines = lines
        self.destination = destination  # Puede ser username o chat ID
        self.sleep_time = sleep_time
        self._stop = False
        self._paused = False

    def stop(self) -> None:
        self._stop = True

    def toggle_pause(self) -> None:
        self._paused = not self._paused

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.send_messages())
        except Exception as e:
            logger.exception("Error en run: %s", e)
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.exception("Error al cancelar tareas: %s", e)
            loop.close()
            logger.debug("Cerrado el loop asyncio en run().")

    async def send_messages(self) -> None:
        async with TelegramClient(SESSION_NAME, api_id, api_hash) as client:
            response_queue: asyncio.Queue = asyncio.Queue()

            # Convertir destino a entero si es numérico
            destination = int(self.destination) if isinstance(self.destination, str) and self.destination.isdigit() else self.destination

            # Configurar el filtro de respuesta basado en el tipo de destino
            if isinstance(destination, int):
                dest_filter = events.NewMessage(chats=destination)
            else:
                dest_filter = events.NewMessage(from_users=destination)

            @client.on(dest_filter)
            async def response_handler(event) -> None:
                await response_queue.put(event.message.message)

            while self.lines and not self._stop:
                while self._paused and not self._stop:
                    await asyncio.sleep(1)
                if self._stop:
                    break

                line = self.lines[0]
                formatted_line = f"{self.prefix} {line}"
                try:
                    await client.send_message(destination, formatted_line)
                    self.lines.pop(0)
                    self.update_data.emit(self.lines)
                except Exception as e:
                    error_msg = f"Error al enviar: {formatted_line} - {e}"
                    self.update_history.emit(error_msg)
                    logger.error(error_msg)
                    await asyncio.sleep(self.sleep_time)
                    continue

                await asyncio.sleep(self.sleep_time)

                try:
                    response = response_queue.get_nowait()
                    if "Status -» Approved! ✅" in response:
                        formatted_response = format_bot_message(response)
                        self.update_history.emit(formatted_response)
                except asyncio.QueueEmpty:
                    pass

            self.finished_sending.emit()

class MessageSenderWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.sender_thread = None
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("Envío de Mensajes a Telegram")
        self.prefix_label = QLabel("Prefijo:")
        self.prefix_entry = QLineEdit()
        self.data_label = QLabel("Datos a enviar:")
        self.data_text_edit = QTextEdit()
        self.data_text_edit.setPlaceholderText("Ingrese los datos aquí, un registro por línea.")
        self.data_text_edit.textChanged.connect(self.manual_update_data)
        
        # Combo para elegir el destino
        self.destination_label = QLabel("Destino:")
        self.destination_combo = QComboBox()
        self.destination_combo.addItem("Bot", bot_username)
        self.destination_combo.addItem("Grupo", str(GROUP_CHAT_ID))
        self.destination_combo.addItem("Bot_1", bot2_username)
        self.destination_combo.addItem("Bot_2", bot3_user)
        self.destination_combo.addItem("Rimuru CHK", str(GROUP_CHAT2_ID))
        
        # SpinBox para seleccionar el tiempo de espera
        self.sleep_label = QLabel("Tiempo de espera (segundos):")
        self.sleep_spinbox = QSpinBox()
        self.sleep_spinbox.setMinimum(1)
        self.sleep_spinbox.setMaximum(60)
        self.sleep_spinbox.setValue(SLEEP_TIME)

        self.start_button = QPushButton("Iniciar envío")
        self.pause_button = QPushButton("Pausar")
        self.stop_button = QPushButton("Detener envío")
        self.load_button = QPushButton("Cargar datos extraídos")
        self.load_button.clicked.connect(self.load_extracted_data)
        self.response_label = QLabel("Respuestas Aprobadas:")
        self.response_widget = QTextEdit()
        self.response_widget.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.prefix_label)
        layout.addWidget(self.prefix_entry)
        layout.addWidget(self.data_label)
        layout.addWidget(self.data_text_edit)
        layout.addWidget(self.destination_label)
        layout.addWidget(self.destination_combo)
        layout.addWidget(self.sleep_label)
        layout.addWidget(self.sleep_spinbox)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.load_button)
        layout.addLayout(button_layout)
        
        layout.addWidget(self.response_label)
        layout.addWidget(self.response_widget)
        self.setLayout(layout)

        self.start_button.clicked.connect(self.start_sending)
        self.pause_button.clicked.connect(self.pause_resume)
        self.stop_button.clicked.connect(self.stop_sending)

    def start_sending(self) -> None:
        prefix = self.prefix_entry.text().strip()
        data_text = self.data_text_edit.toPlainText().strip()
        if not prefix or not data_text:
            self.show_error("Por favor, ingrese el prefijo y los datos.")
            return
        lines = [line.strip() for line in data_text.splitlines() if line.strip()]
        if not lines:
            self.show_error("No se encontraron datos para enviar.")
            return
        
        destination = self.destination_combo.currentData()
        sleep_time = self.sleep_spinbox.value()
        self.sender_thread = MessageSenderThread(prefix, lines, destination, sleep_time)
        self.sender_thread.update_history.connect(self.append_response)
        self.sender_thread.update_data.connect(self.update_data_text)
        self.sender_thread.finished_sending.connect(lambda: self.append_response("Proceso finalizado."))
        self.sender_thread.start()

    def pause_resume(self) -> None:
        if self.sender_thread:
            self.sender_thread.toggle_pause()
            self.pause_button.setText("Continuar" if self.sender_thread._paused else "Pausar")
        else:
            self.append_response("No hay proceso en ejecución para pausar o reanudar.")

    def stop_sending(self) -> None:
        if self.sender_thread:
            self.sender_thread.stop()
            self.append_response("Proceso detenido por el usuario.")
        else:
            self.append_response("No hay proceso en ejecución.")

    def append_response(self, message: str) -> None:
        self.response_widget.append(message)

    def update_data_text(self, lines: List[str]) -> None:
        self.data_text_edit.setPlainText("\n".join(lines))

    def manual_update_data(self) -> None:
        if not self.sender_thread or (self.sender_thread and not self.sender_thread.isRunning()):
            lines = [line.strip() for line in self.data_text_edit.toPlainText().splitlines() if line.strip()]
            if self.sender_thread:
                self.sender_thread.lines = lines

    def load_extracted_data(self) -> None:
        try:
            messages = get_extracted_messages()
            if messages:
                self.data_text_edit.setPlainText("\n".join(messages))
                self.append_response("Datos extraídos cargados exitosamente.")
            else:
                self.append_response("No hay datos extraídos disponibles.")
        except Exception as e:
            self.show_error(f"Error al cargar datos extraídos: {e}")

    def show_error(self, message: str) -> None:
        error_dialog = QErrorMessage(self)
        error_dialog.showMessage(message)
        error_dialog.exec_()
