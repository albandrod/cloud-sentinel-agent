"""
Script para reprocesar todas las noticias de la BBDD con el nuevo scoring avanzado y clasificación multicategoría.
"""
import logging
from tools.db_tools import get_all_events
from agents.analyst import analyst_node
from schema.state import AgentState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reanaliza_noticias")


def _update_event_analysis(content_hash, analysis):
    import sqlite3, json
    from tools.db_tools import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        with conn:
            cursor.execute("""
                UPDATE events 
                SET analysis_json = ?, is_processed = 1 
                WHERE content_hash = ?
            """, (json.dumps(analysis), content_hash))
    except Exception as e:
        logger.error(f"❌ Error actualizando análisis para {content_hash}: {e}")
    finally:
        conn.close()

def main():
    logger.info("Leyendo todas las noticias de la base de datos...")
    noticias = get_all_events()
    logger.info(f"Total noticias encontradas: {len(noticias)}")

    # Estado simulado para el analyst (sin filtros, todas las categorías y keywords)
    state = AgentState(
        clouds=[],
        categories=[],
        keywords=[],
        pending_news=noticias,
        max_news_to_process=len(noticias)
    )
    logger.info("Ejecutando analyst_node para reprocesar...")
    resultado = analyst_node(state)
    analizadas = resultado.get("analyzed_news", [])
    logger.info(f"Noticias reprocesadas: {len(analizadas)}")

    for n in analizadas:
        content_hash = n.get("content_hash")
        analysis = n.get("analysis")
        if content_hash and analysis:
            _update_event_analysis(content_hash, analysis)
    logger.info("Reprocesado y actualización completados.")

if __name__ == "__main__":
    main()
