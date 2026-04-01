from langchain_core.tools import tool
import sqlite3

@tool
def check_existing_events(event_hashes: List[str]):
    """
    Comprueba en la base de datos local cuáles de estos hashes ya han sido procesados.
    Útil para que el Collector no duplique trabajo.
    """
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()
    # Lógica para devolver solo los hashes que NO están en la DB
    # (Usaremos la lógica que ya tenías en db.py)
    conn.close()
    return list_de_hashes_nuevos