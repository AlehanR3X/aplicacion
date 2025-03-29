#data_manager
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = 'messages.db'

def get_extracted_messages():
    """Devuelve una lista con todos los mensajes extraídos (solo el dato filtrado)."""
    messages = []
    try:
        # Se utiliza 'with' para asegurar el cierre automático de la conexión.
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message FROM messages")
            rows = cursor.fetchall()
            messages = [row[0] for row in rows]
    except sqlite3.Error as e:
        logger.error("Error en la base de datos: %s", e)
    except Exception as e:
        logger.exception("Error inesperado: %s", e)
    return messages

def clear_extracted_messages():
    """Elimina todos los mensajes extraídos de la base de datos."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Error en la base de datos: %s", e)
    except Exception as e:
        logger.exception("Error inesperado: %s", e)
