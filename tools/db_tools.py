import sqlite3
import json
import os
from typing import List, Dict, Any
from langchain_core.tools import tool

DB_PATH = "cloud_sentinel.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT,
            link TEXT UNIQUE,
            full_content TEXT,
            published_at TEXT,
            content_hash TEXT,
            analysis_json TEXT,
            is_processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente.")

@tool
def save_raw_news(news_list: List[Dict[str, Any]]):
    """
    Guarda una lista de noticias en bruto en la base de datos.
    """
    if not news_list: return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for item in news_list:
        try:
            # Priorizamos 'body' o 'full_content' que venga del Collector
            content = item.get('body') or item.get('full_content') or ""
            cursor.execute('''
                INSERT OR IGNORE INTO events 
                (content_hash, source, title, link, published_at, full_content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (item['content_hash'], item['source'], item['title'], 
                  item['link'], item['published_at'], content))
        except Exception as e:
            print(f"❌ Error guardando hash {item.get('content_hash')}: {e}")
    conn.commit()
    conn.close()

@tool
def update_event_analysis(content_hash: str, analysis: Dict[str, Any]):
    """
    Actualiza el campo analysis_json de una noticia usando su content_hash.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE events 
        SET analysis_json = ?, is_processed = 1 
        WHERE content_hash = ?
    """, (json.dumps(analysis), content_hash))
    conn.commit()
    conn.close()

@tool
def get_unprocessed_events(limit: int = 15) -> List[Dict]:
    """Trae noticias sin procesar, priorizando siempre las más RECIENTES."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # IMPORTANTE: ORDER BY published_at DESC
    cursor.execute("""
        SELECT * FROM events 
        WHERE is_processed = 0 
        ORDER BY published_at DESC 
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@tool
def get_analyzed_events(limit: int = 50) -> List[Dict]:
    """
    Recupera noticias que ya tienen un análisis técnico en la base de datos.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE analysis_json IS NOT NULL ORDER BY published_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@tool
def filter_new_hashes(hashes: List[str]) -> List[str]:
    """
    Recibe una lista de hashes y devuelve solo aquellos que NO están en la base de datos.
    Sirve para evitar procesar noticias duplicadas.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if not hashes:
        return []
        
    # Creamos los placeholders (?,?,?) para la consulta SQL
    placeholders = ', '.join(['?'] * len(hashes))
    query = f"SELECT content_hash FROM events WHERE content_hash IN ({placeholders})"
    
    cursor.execute(query, hashes)
    existing_hashes = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    # Devolvemos solo los que no existen en la DB
    return [h for h in hashes if h not in existing_hashes]