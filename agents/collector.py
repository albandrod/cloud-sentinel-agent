import itertools
import concurrent.futures
import logging
import os
from typing import Dict, Any, List
from datetime import datetime
from schema.state import AgentState
from tools.search_tools import AzureCollector, AWSCollector, GCPCollector
from tools.db_tools import filter_new_hashes, save_raw_news

def normalize_news_item(news: dict) -> dict:
    """Normaliza campos clave de la noticia."""
    item = dict(news)
    # Normaliza fuente
    if 'source' in item:
        item['source'] = item['source'].strip().lower()
    # Normaliza fecha: published_at SIEMPRE en formato ISO (YYYY-MM-DD)
    fecha = None
    if 'published_date' in item:
        try:
            dt = item['published_date']
            if isinstance(dt, str):
                dt = dt.replace('Z', '+00:00')
                fecha = datetime.fromisoformat(dt)
            elif isinstance(dt, datetime):
                fecha = dt
        except Exception:
            pass
    if not fecha:
        fecha = datetime.now()
    # published_at en formato YYYY-MM-DD
    item['published_at'] = fecha.strftime('%Y-%m-%d')
    # published_date también en ISO completo por si se usa en otros sitios
    item['published_date'] = fecha.isoformat()
    # Normaliza título y contenido
    if 'title' in item:
        item['title'] = item['title'].strip()
    if 'full_content' in item:
        item['full_content'] = item['full_content'].strip()
    return item

def collector_node(state: AgentState) -> Dict[str, Any]:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("collector")
    logger.info("--- 🕵️‍♂️ INICIANDO COLLECTOR AGENT (Multi-Cloud Parallel) ---")

    # Configuración: fuentes y parámetros
    max_workers = int(os.getenv("COLLECTOR_MAX_WORKERS", "3"))
    sources = state.get("sources") or ["Azure", "AWS", "GCP"]

    # 1. EJECUCIÓN EN PARALELO (MULTITHREADING)
    all_news_raw = []
    logger.info(f"📡 Iniciando barrido concurrente de {', '.join(sources)}...")

    cloud_funcs = {
        "Azure": lambda _: AzureCollector.fetch_all(days=3),
        "AWS": lambda _: AWSCollector.fetch_all(days=3),
        "GCP": lambda _: GCPCollector.fetch_all(days=3)
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_cloud = {
            executor.submit(cloud_funcs[cloud], {}): cloud for cloud in sources if cloud in cloud_funcs
        }
        results = {cloud: [] for cloud in sources}
        for future in concurrent.futures.as_completed(future_to_cloud):
            cloud_name = future_to_cloud[future]
            try:
                data = future.result()
                results[cloud_name] = data if data else []
                logger.info(f"  ✅ {cloud_name} finalizado: {len(results[cloud_name])} items.")
            except Exception as e:
                logger.error(f"  ❌ Error en colector de {cloud_name}: {e}")
                results[cloud_name] = []


    # 2. LÓGICA DE INTERCALADO (ROUND ROBIN)
    news_lists = [results[cloud] for cloud in sources if cloud in results]
    for items in itertools.zip_longest(*news_lists):
        for item in items:
            if item:
                all_news_raw.append(item)

    logger.info(f"[DEBUG] Total items crudos recolectados de feeds: {len(all_news_raw)}")
    if all_news_raw:
        for i, n in enumerate(all_news_raw[:10]):
            logger.info(f"[DEBUG] Ejemplo noticia {i+1}: hash={n.get('content_hash','')} | título={n.get('title','')[:60]}")

    if not all_news_raw:
        logger.warning("🛑 Alerta CCOE: No se ha obtenido información de ninguna fuente.")
        return {"next_step": "end", "raw_news": []}

    # 3. FILTRADO POR HASH (SEGURIDAD Y EFICIENCIA)
    logger.info("🔍 Validando novedades contra la base de datos...")
    try:
        all_hashes = [news["content_hash"] for news in all_news_raw if "content_hash" in news]
        logger.info(f"[DEBUG] Hashes recolectados: {all_hashes[:10]}{'...' if len(all_hashes)>10 else ''}")
        new_hashes = filter_new_hashes.invoke({"hashes": all_hashes})
        logger.info(f"[DEBUG] Hashes NUEVOS tras filtro: {new_hashes[:10]}{'...' if len(new_hashes)>10 else ''}")
    except Exception as e:
        logger.error(f"❌ Error en validación de hashes: {e}")
        return {"next_step": "end", "raw_news": []}

    if not new_hashes:
        logger.info("✅ Infraestructura al día. No hay noticias nuevas por procesar.")
        return {"raw_news": [], "next_step": "analyze"}

    # 4. PREPARACIÓN Y NORMALIZACIÓN DE NOVEDADES

    # Añadir logs de descarte por campos obligatorios
    new_news_items = []
    descartadas = 0
    for news in all_news_raw:
        if news.get("content_hash") in new_hashes:
            norm = normalize_news_item(news)
            # Comprobación de campos obligatorios
            missing = []
            if not norm.get("content_hash"): missing.append("content_hash")
            if not norm.get("link"): missing.append("link")
            if not norm.get("title"): missing.append("title")
            if missing:
                logger.warning(f"Noticia descartada por falta de campos: {missing} | Título: {norm.get('title','')} | Link: {norm.get('link','')}")
                descartadas += 1
                continue
            new_news_items.append(norm)
    logger.info(f"🟢 Identificadas {len(new_news_items)} noticias inéditas. Descartadas por campos incompletos: {descartadas}")

    # 5. PERSISTENCIA EN DB (paralelizada por lotes)
    def save_batch(news_batch):
        try:
            save_raw_news.invoke({"news_list": news_batch})
            logger.info(f"💾 Lote de {len(news_batch)} noticias persistido correctamente.")
        except Exception as e:
            logger.error(f"❌ Error al guardar lote en DB: {e}")

    batch_size = int(os.getenv("COLLECTOR_BATCH_SIZE", "20"))
    batches = [new_news_items[i:i+batch_size] for i in range(0, len(new_news_items), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(batches))) as executor:
        futures = [executor.submit(save_batch, batch) for batch in batches]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    return {
        "raw_news": new_news_items,
        "next_step": "analyze"
    }