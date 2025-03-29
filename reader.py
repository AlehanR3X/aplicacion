#reader
import asyncio
import threading
import logging

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt5.QtCore import QTimer
from telegram.ext import Application, MessageHandler, filters

from config import TARGET_CHAT_ID, TOKEN, DATA_FILE

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def extract_information(message_text: str) -> str:
    """
    Extrae datos formateados de un mensaje utilizando expresiones regulares.
    Retorna la información extraída o un mensaje indicando que no se encontró patrón.
    """
    import re
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

def run_bot() -> None:
    """
    Configura y ejecuta el bot de Telegram, filtrando mensajes del chat objetivo y 
    almacenando la información extraída en un archivo.
    """
    # Se crea un nuevo loop para la ejecución asíncrona en un hilo separado
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def save_message(update, context) -> None:
        try:
            if update.message:
                chat_id = update.message.chat.id
                if chat_id == TARGET_CHAT_ID:
                    if update.message.text:
                        extracted_info = extract_information(update.message.text)
                    else:
                        extracted_info = "<Patrón no encontrado>"
                    try:
                        with open(DATA_FILE, "a", encoding="utf-8") as f:
                            f.write(f"{extracted_info}\n")
                    except Exception as file_err:
                        logger.error("Error al escribir en el archivo: %s", file_err)
                    logger.info("Mensaje extraído: %s", extracted_info)
                else:
                    logger.debug("Mensaje recibido de chat distinto: %s", chat_id)
        except Exception as e:
            logger.error("Error en save_message: %s", e, exc_info=True)
    
    try:
        app_bot = Application.builder().token(TOKEN).build()
        app_bot.add_handler(MessageHandler(filters.ALL, save_message))
        logger.info("Bot iniciado, escuchando mensajes...")
        app_bot.run_polling()
    except Exception as e:
        logger.error("Error al iniciar el bot: %s", e, exc_info=True)

class ModoLectorWidget(QWidget):
    """
    Widget para visualizar en tiempo real los datos extraídos por el bot.
    Permite iniciar el bot y limpiar el archivo de datos.
    """
    def __init__(self) -> None:
        super().__init__()
        self.init_ui()
        # Se usa un QTimer para actualizar el contenido del archivo cada 1 segundo.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_log_from_file)
        self.timer.start(1000)

    def init_ui(self) -> None:
        self.setWindowTitle("Telegram Bot - Datos Extraídos")
        layout = QVBoxLayout()

        self.file_label = QLabel(f"Archivo: {DATA_FILE}")
        layout.addWidget(self.file_label)

        botones_layout = QHBoxLayout()
        self.start_button = QPushButton("Iniciar Bot")
        self.start_button.clicked.connect(self.start_bot)
        self.clear_button = QPushButton("Borrar datos")
        self.clear_button.clicked.connect(self.clear_log)
        botones_layout.addWidget(self.start_button)
        botones_layout.addWidget(self.clear_button)
        layout.addLayout(botones_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def start_bot(self) -> None:
        """Inicia el bot en un hilo separado para no bloquear la interfaz."""
        self.start_button.setEnabled(False)
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("Hilo del bot iniciado.")

    def update_log_from_file(self) -> None:
        """Lee el contenido del archivo y actualiza el widget de texto."""
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            self.log_output.setPlainText(content)
        except FileNotFoundError:
            self.log_output.setPlainText("")
        except Exception as e:
            logger.error("Error al actualizar log: %s", e)

    def clear_log(self) -> None:
        """Limpia el contenido del widget y del archivo de datos."""
        self.log_output.clear()
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                f.write("")
            logger.info("Archivo de datos limpiado.")
        except Exception as e:
            logger.error("Error al borrar el archivo: %s", e)
