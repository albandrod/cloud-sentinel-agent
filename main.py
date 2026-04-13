
import os
import sqlite3
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. Cargar configuración
load_dotenv(override=True)

from tools.db_tools import init_db, get_unprocessed_events, get_analyzed_events
from agents.collector import collector_node
from agents.analyst import analyst_node
from agents.writer import writer_node

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# 1. Cargar configuración
load_dotenv(override=True)

from tools.db_tools import init_db, get_unprocessed_events, get_analyzed_events
from agents.collector import collector_node
from agents.analyst import analyst_node
from agents.writer import writer_node

def validate_news_list(news_list):
    if not isinstance(news_list, list):
        logger.error("El resultado no es una lista de noticias.")
        return []
    valid = [n for n in news_list if isinstance(n, dict) and n.get("title") and n.get("link")]
    if len(valid) != len(news_list):
        logger.warning(f"Noticias descartadas por formato inválido: {len(news_list) - len(valid)}")
    return valid

def run_sentinel_orchestrator():
    # Permitir que el usuario ajuste el umbral de relevancia vía prompt
    relevance_threshold = None
    report_type = None
    lang = "es"
    try:
        lang = state.get("lang", "es")
    except Exception:
        pass
    # Obtener el prompt del usuario de argumento, input interactivo o variable de entorno
    import sys
    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = input("¿Qué informe deseas generar? (Ej: Informe técnico de Azure sobre seguridad y costes, últimos 15 días): ").strip()
    prompt_lower = user_prompt.lower()
    match_relevance = re.search(r"relevancia (mínima|minimo|minima|min) ?(\d+)", prompt_lower)
    if not match_relevance:
        match_relevance = re.search(r"minimum relevance ?(\d+)", prompt_lower)
    if match_relevance:
        relevance_threshold = int(match_relevance.group(2) if match_relevance.lastindex == 2 else match_relevance.group(1))
    """
    Orquestador Cloud Sentinel:
    1. Sincroniza noticias nuevas (Collector).
    2. Analiza el backlog pendiente (Analyst - Fase Ingesta).
    3. Filtra el historial del último mes según el prompt (Analyst - Fase Recuperación).
    """
    logger.info("\n" + "="*50)
    logger.info("🛰️  CLOUD SENTINEL: SISTEMA DE INTELIGENCIA")
    logger.info("="*50)
    try:
        prompt_lower = user_prompt.lower()
        init_db()
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")
        # PASO 4: Generación de Reporte (Writer Agent)
        # Usar directamente el historial completo recuperado de la BBDD para el informe
        if full_history:
            logger.info(f"✅ RELEVANCIA ENCONTRADA: {len(full_history)} noticias coinciden con tu interés.")
            writer_state = {
                "analyzed_news": full_history,
                "user_instructions": user_prompt,
                "report_type": report_type,
                "lang": lang,
                "categories": categories,
                "keywords": keywords
            }
            try:
                writer_node(writer_state)
            except Exception as e:
                logger.error(f"Error en writer_node: {e}")
        else:
            logger.warning("❌ No se encontraron noticias relevantes para el informe.")


    # Definir tipo_map antes de su uso
    tipo_map = {
        "tecnico": "Técnico",
        "técnico": "Técnico",
        "ejecutivo": "Ejecutivo",
        "resumen": "Resumen",
        "completo": "Completo",
        "personalizado": "Personalizado"
    }
    # Extraer tipo de informe explícito si existe
    for k, v in tipo_map.items():
        if f"informe {k}" in prompt_lower or prompt_lower.strip().endswith(k) or k in prompt_lower:
            report_type = v
            break

    # Si el prompt pide "technical report" o "technical" en inglés, forzar tipo técnico
    if ("technical report" in prompt_lower or "technical" in prompt_lower) and lang == "en":
        report_type = "Técnico"

    # Si no se detecta tipo, por defecto Ejecutivo
    if not report_type:
        report_type = "Ejecutivo"

    # Normalizar tipo de informe a minúsculas y sin tildes para el writer
    import unicodedata
    def normalize_type(t):
        t = t.lower()
        t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('ascii')
        return t
    report_type = normalize_type(report_type)

    # Límite de noticias para histórico (ya procesadas)
    limit_historico = 750  # valor por defecto
    match_limit = re.search(r"maxim[oa] ?(\d+)", prompt_lower)
    if match_limit:
        limit_historico = int(match_limit.group(1))
    # Límite para pendientes (sin procesar): igual al límite del Analyst
    limit_pendientes = 30

    # Ventana temporal flexible: soporta "últimos X días", "últimas X semanas", "quince días", "dos semanas", etc.
    days_to_look = None
    # 1. "10 días", "15 dias"
    match = re.search(r"(\d{1,3})\s*d[ií]as?", prompt_lower)
    if match:
        days_to_look = int(match.group(1))
    else:
        # 2. "últimos X días"
        match2 = re.search(r"últim[oa]s?\s+(\d{1,3})\s*d[ií]as?", prompt_lower)
        if match2:
            days_to_look = int(match2.group(1))
        else:
            # 3. "últimas X semanas"
            match3 = re.search(r"últim[oa]s?\s+(\d{1,2})\s*semana[s]?", prompt_lower)
            if match3:
                days_to_look = int(match3.group(1)) * 7
            else:
                # 4. "últimos X meses"
                match4 = re.search(r"últim[oa]s?\s+(\d{1,2})\s*mes(es)?", prompt_lower)
                if match4:
                    days_to_look = int(match4.group(1)) * 30
                else:
                    # 5. Palabras clave
                    if "quince días" in prompt_lower or "quince dias" in prompt_lower:
                        days_to_look = 15
                    elif "dos semanas" in prompt_lower:
                        days_to_look = 14
                    elif any(word in prompt_lower for word in ["semana", "7 días", "7 dias", "last week"]):
                        days_to_look = 7
                    elif any(word in prompt_lower for word in ["mes", "30 días", "30 dias"]):
                        days_to_look = 30

    # Filtros por fuente (tolerante a mayúsculas/minúsculas y typos)
    def fuzzy_source_map(word):
        word = word.lower()
        if any(x in word for x in ["azure", "azur", "azr", "azue"]):
            return "Azure"
        if any(x in word for x in ["aws", "amazon", "awz", "was"]):
            return "AWS"
        if any(x in word for x in ["gcp", "google", "gco", "gcp", "goolge", "gogle"]):
            return "GCP"
        return None

    sources = []
    for token in re.split(r"[ ,;/\n]+", prompt_lower):
        mapped = fuzzy_source_map(token)
        if mapped and mapped not in sources:
            sources.append(mapped)
    # Si no se detecta ninguna fuente, usar todas
    if not sources:
        sources = ["Azure", "AWS", "GCP"]

    # Filtros por categoría
    categories = []
    if "coste" in prompt_lower or "cost" in prompt_lower: categories.append("Cost")
    if "seguridad" in prompt_lower or "security" in prompt_lower: categories.append("Security")
    if "arquitectura" in prompt_lower or "architecture" in prompt_lower: categories.append("Architecture")
    if "general" in prompt_lower: categories.append("General")

    # Palabras clave adicionales: extraer palabras relevantes del prompt
    keywords = []
    # Heurística: extraer palabras entre comillas, después de 'sobre', 'about', 'relating to', o tras 'palabra clave', etc.
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”|‘([^’]+)’', prompt_lower)
    for group in quoted:
        for kw in group:
            if kw:
                keywords.append(kw.strip())
    # También extraer palabras tras 'sobre', 'about', 'relating to', etc.
    match_kw = re.search(r'(?:sobre|about|relating to|palabra clave|keywords?)\s*([\w\s,\-]+)', prompt_lower)
    if match_kw:
        # Separar por coma o espacio
        for kw in re.split(r',| y | and |/|\n', match_kw.group(1)):
            kw = kw.strip()
            if kw and kw not in keywords:
                keywords.append(kw)
    # Limpiar duplicados y palabras vacías
    keywords = list({k.strip() for k in keywords if k.strip()})
    # Extraer tipo de informe
    report_type = "Ejecutivo"
    tipo_map = {
        "tecnico": "Técnico",
        "técnico": "Técnico",
        "ejecutivo": "Ejecutivo",
        "resumen": "Resumen",
        "completo": "Completo",
        "personalizado": "Personalizado"
    }
    for k, v in tipo_map.items():
        if f"informe {k}" in prompt_lower or prompt_lower.strip().endswith(k):
            report_type = v
            break
    # Si el prompt pide "technical report" o "technical" en inglés, forzar tipo técnico
    if ("technical report" in prompt_lower or "technical" in prompt_lower) and lang == "en":
        report_type = "Técnico"

    # PASO 1: Ingesta de nuevas noticias (Collector)
    logger.info("[1/3] Sincronizando fuentes externas (Azure, AWS, GCP)...")
    try:
        collector_node({"raw_news": [], "sources": sources})
    except Exception as e:
        logger.error(f"Error en collector_node: {e}")

    # PASO 2: Procesamiento de noticias "vírgenes"
    logger.info("🧠 Procesando backlog de noticias sin analizar...")
    try:
        pending_args = {"limit": limit_pendientes}
        if "azure" in prompt_lower or "aws" in prompt_lower or "gcp" in prompt_lower or "google" in prompt_lower:
            if sources and len(sources) == 1:
                pending_args["source"] = sources[0]
        if days_to_look:
            pending_args["from_date"] = (datetime.now() - timedelta(days=days_to_look)).strftime('%Y-%m-%d')
        pending = get_unprocessed_events.invoke(pending_args)
        logger.info(f"[DEBUG] Noticias pendientes recuperadas de BBDD: {len(pending) if pending else 0}")
        pending = validate_news_list(pending)
        logger.info(f"[DEBUG] Noticias pendientes tras validación: {len(pending) if pending else 0}")
    except Exception as e:
        logger.error(f"Error obteniendo noticias pendientes: {e}")
        pending = []

    if pending:
        logger.info(f"-> El Analyst está enriqueciendo {len(pending)} noticias nuevas...")
        state_ingesta = {
            "raw_news": pending,
            "analyzed_news": [],
            "user_instructions": user_prompt,
            "report_type": report_type,
            "lang": lang,
            "categories": categories,
            "keywords": keywords,
            "relevance_threshold": relevance_threshold
        }
        try:
            analyst_node(state_ingesta)
        except Exception as e:
            logger.error(f"Error en analyst_node (ingesta): {e}")
    else:
        logger.info("✅ No hay noticias nuevas para analizar en el backlog.")

    # PASO 3: Recuperación de Memoria Histórica (El "Cerebro")
    logger.info("[3/3] Consultando memoria histórica (últimos 30 días)...")
    try:
        history_args = {"limit": limit_historico}
        if "azure" in prompt_lower or "aws" in prompt_lower or "gcp" in prompt_lower or "google" in prompt_lower:
            if sources and len(sources) == 1:
                history_args["source"] = sources[0]
        if days_to_look:
            history_args["from_date"] = (datetime.now() - timedelta(days=days_to_look)).strftime('%Y-%m-%d')
        if categories and ("coste" in prompt_lower or "cost" in prompt_lower or "seguridad" in prompt_lower or "security" in prompt_lower or "arquitectura" in prompt_lower or "architecture" in prompt_lower or "general" in prompt_lower):
            if len(categories) == 1:
                history_args["search"] = categories[0]
        full_history = get_analyzed_events.invoke(history_args)
        logger.info(f"[DEBUG] Noticias analizadas recuperadas de BBDD: {len(full_history) if full_history else 0}")
        full_history = validate_news_list(full_history)
        logger.info(f"[DEBUG] Noticias analizadas tras validación: {len(full_history) if full_history else 0}")
    except Exception as e:
        logger.error(f"Error consultando memoria histórica: {e}")
        full_history = []

    state_recovery = {
        "raw_news": full_history,
        "analyzed_news": [],
        "user_instructions": user_prompt,
        "report_type": report_type,
        "lang": lang,
        "categories": categories,
        "keywords": keywords,
        "relevance_threshold": relevance_threshold
    }
    try:
        final_state = analyst_node(state_recovery)
    except Exception as e:
        logger.error(f"Error en analyst_node (recovery): {e}")
        final_state = {}

    # PASO 4: Generación de Reporte (Writer Agent)
    analyzed_news = final_state.get("analyzed_news") if isinstance(final_state, dict) else None
    if analyzed_news:
        num_noticias = len(analyzed_news)
        logger.info(f"✅ RELEVANCIA ENCONTRADA: {num_noticias} noticias coinciden con tu interés.")
        try:
            writer_node(final_state)
        except Exception as e:
            logger.error(f"Error en writer_node: {e}")
    else:
        logger.warning("No se han encontrado noticias que coincidan con tu búsqueda en el último mes.")

if __name__ == "__main__":
    run_sentinel_orchestrator()