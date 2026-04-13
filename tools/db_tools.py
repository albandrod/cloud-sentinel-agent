def get_all_events() -> list:
    """Devuelve todas las noticias de la tabla events como lista de diccionarios."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM events")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error en get_all_events: {e}")
        return []
    finally:
        conn.close()
import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

DB_PATH = "cloud_sentinel.db"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_tools")

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_published ON events (published_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed ON events (is_processed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON events (source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON events (content_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON events (title)")
    conn.commit()
    conn.close()
    logger.info("✅ Base de datos inicializada y optimizada.")

def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return str(text).strip()

def _clean_date(date_str: Optional[str]) -> str:
    if not date_str:
        return datetime.now().strftime('%Y-%m-%d')
    # Si ya es YYYY-MM-DD
    import re
    if re.match(r"\d{4}-\d{2}-\d{2}", str(date_str)):
        return str(date_str)[:10]
    # Intenta usar dateutil si está disponible
    try:
        from dateutil import parser
        dt = parser.parse(str(date_str), fuzzy=True, default=datetime.now())
        return dt.strftime('%Y-%m-%d')
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback manual para formatos tipo 'Wed, 08 Apr'
    try:
        for fmt in ["%a, %d %b", "%a, %d %B", "%d %b %Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(str(date_str), fmt)
                if dt.year == 1900:
                    dt = dt.replace(year=datetime.now().year)
                return dt.strftime('%Y-%m-%d')
            except Exception:
                continue
    except Exception:
        pass
    # Si todo falla, devuelve la fecha actual
    return datetime.now().strftime('%Y-%m-%d')

@tool
def save_raw_news(news_list: List[Dict[str, Any]]):
    """Guarda noticias en bruto con limpieza de fechas y títulos. Inserta en transacción y valida campos."""
    if not news_list:
        logger.info("[save_raw_news] Lista de noticias vacía, nada que guardar.")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        with conn:
            to_insert = []
            for idx, item in enumerate(news_list):
                title = _clean_text(item.get('title', ''))
                # Filtro de versiones (v1.0, etc)
                if any(char.isdigit() for char in title) and ("v" in title.lower() or "." in title):
                    if len(title) < 15:
                        logger.info(f"[save_raw_news] Descartada por título corto con versión: {title}")
                        continue
                published_at = item.get('published_at', '') or item.get('published_date', '')
                if published_at:
                    import re
                    if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", str(published_at)):
                        clean_date = published_at
                    else:
                        clean_date = _clean_date(published_at)
                else:
                    clean_date = _clean_date('')
                content = _clean_text(item.get('body') or item.get('full_content') or "")
                content_hash = _clean_text(item.get('content_hash', ''))
                source = _clean_text(item.get('source', ''))
                src = source.lower()
                if src in ["google", "google cloud", "gcp"] or "google" in src:
                    source = "gcp"
                elif src in ["amazon", "aws"] or "amazon" in src:
                    source = "aws"
                elif src in ["microsoft", "azure"] or "microsoft" in src:
                    source = "azure"
                link = _clean_text(item.get('link', ''))
                # Log detallado de cada intento de inserción
                logger.info(f"[save_raw_news] Preparando noticia {idx+1}: hash={content_hash} | fuente={source} | fecha={clean_date} | título={title[:60]} | link={link}")
                if not content_hash or not link or not title:
                    logger.warning(f"[save_raw_news] Noticia descartada por datos incompletos: hash={content_hash} | título={title[:60]} | link={link}")
                    continue
                to_insert.append((content_hash, source, title, link, clean_date, content))
            logger.info(f"[save_raw_news] Total candidatas a insertar: {len(to_insert)}")
            cursor.executemany('''
                INSERT OR IGNORE INTO events 
                (content_hash, source, title, link, published_at, full_content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', to_insert)
        logger.info(f"[save_raw_news] Guardadas {len(to_insert)} noticias nuevas (INSERT OR IGNORE).")
    except Exception as e:
        logger.error(f"❌ Error guardando noticias: {e}")
    finally:
        conn.close()

@tool
def update_event_analysis(content_hash: str, analysis: Dict[str, Any]):
    """Guarda el análisis y marca como procesado. Maneja errores y logging."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        with conn:
            cursor.execute("""
                UPDATE events 
                SET analysis_json = ?, is_processed = 1 
                WHERE content_hash = ?
            """, (json.dumps(analysis), content_hash))
        logger.info(f"Análisis guardado para hash: {content_hash}")
    except Exception as e:
        logger.error(f"❌ Error actualizando análisis para {content_hash}: {e}")
    finally:
        conn.close()

@tool
def get_unprocessed_events(limit: int = 40, source: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, page: int = 1) -> List[Dict]:
    """Trae noticias que la IA aún no ha enriquecido. Permite paginación y filtros por fuente y fechas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    frescura_limite = from_date or (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
    params = [frescura_limite]
    query = "SELECT * FROM events WHERE is_processed = 0 AND published_at >= ?"
    if source:
        query += " AND LOWER(source) = ?"
        params.append(source.lower())
    if to_date:
        query += " AND published_at <= ?"
        params.append(to_date)
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, (page-1)*limit])
    try:
        # Log de depuración: cuántas noticias hay en total y su estado
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE is_processed = 0")
        sin_procesar = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE is_processed = 1")
        procesadas = cursor.fetchone()[0]
        logger.info(f"[DB-DEBUG] Total noticias en tabla: {total} | Sin procesar: {sin_procesar} | Procesadas: {procesadas}")
        cursor.execute("SELECT published_at, is_processed FROM events ORDER BY published_at DESC LIMIT 10")
        ultimas = cursor.fetchall()
        logger.info(f"[DB-DEBUG] Últimas fechas y estado: {[dict(row) for row in ultimas]}")
        # NUEVO: Mostrar las 10 últimas noticias sin procesar
        cursor.execute("SELECT id, published_at, title FROM events WHERE is_processed = 0 ORDER BY published_at DESC LIMIT 10")
        ultimas_no_proc = cursor.fetchall()
        logger.info(f"[DB-DEBUG] Últimas 10 sin procesar: {[dict(row) for row in ultimas_no_proc]}")
        # Consulta real
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[DB-DEBUG] get_unprocessed_events devuelve: {len(rows)} registros")
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error en get_unprocessed_events: {e}")
        return []
    finally:
        conn.close()

@tool
def get_analyzed_events(limit: int = 100, days: int = 30, source: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, page: int = 1, search: Optional[str] = None) -> List[Dict]:
    """
    Motor de búsqueda histórico. Permite paginación, búsqueda por texto, fuente y rango de fechas.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    fecha_limite = from_date or (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    params = [fecha_limite]
    query = "SELECT * FROM events WHERE analysis_json IS NOT NULL AND published_at >= ?"
    if source:
        query += " AND LOWER(source) = ?"
        params.append(source.lower())
    if to_date:
        query += " AND published_at <= ?"
        params.append(to_date)
    if search:
        query += " AND (title LIKE ? OR full_content LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, (page-1)*limit])
    try:
        # Log de depuración: cuántas noticias hay en total y su estado
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE is_processed = 0")
        sin_procesar = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE is_processed = 1")
        procesadas = cursor.fetchone()[0]
        logger.info(f"[DB-DEBUG] Total noticias en tabla: {total} | Sin procesar: {sin_procesar} | Procesadas: {procesadas}")
        cursor.execute("SELECT published_at, is_processed FROM events ORDER BY published_at DESC LIMIT 10")
        ultimas = cursor.fetchall()
        logger.info(f"[DB-DEBUG] Últimas fechas y estado: {[dict(row) for row in ultimas]}")
        # Consulta real
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[DB-DEBUG] get_analyzed_events devuelve: {len(rows)} registros")
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error en get_analyzed_events: {e}")
        return []
    finally:
        conn.close()

@tool
def filter_new_hashes(hashes: List[str]) -> List[str]:
    """Evita duplicados antes de insertar. Optimizado para lotes grandes."""
    if not hashes:
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        placeholders = ', '.join(['?'] * len(hashes))
        cursor.execute(f"SELECT content_hash FROM events WHERE content_hash IN ({placeholders})", hashes)
        existing = {row[0] for row in cursor.fetchall()}
        return [h for h in hashes if h not in existing]
    except Exception as e:
        logger.error(f"Error en filter_new_hashes: {e}")
        return hashes
    finally:
        conn.close()