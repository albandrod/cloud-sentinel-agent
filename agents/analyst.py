import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import logging
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schema.state import AgentState
from tools.db_tools import update_event_analysis

# Configuración centralizada de logging para el nodo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analyst")

def normalize_source(source: str) -> str:
    """Normaliza el nombre del proveedor/fuente."""
    return source.lower().strip() if source else ""

def parse_date(date_str: str) -> datetime:
    """Intenta parsear la fecha en varios formatos comunes."""
    if not date_str:
        return None
    try:
        clean_date = date_str.replace('Z', '+00:00')
        return datetime.fromisoformat(clean_date)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    return None

# =====================
# ANALYST NODE (module level)
# =====================
def analyst_node(state: AgentState) -> Dict[str, Any]:
    logger.info("\n--- 🧠 INICIANDO ANALYST AGENT (Filtro Dinámico Multi-Cloud) ---")
    debug_mode = os.getenv("DEBUG_MODE", "0") == "1" or state.get("debug_mode")


    # Filtrar por cloud/source si se especifica en el estado
    clouds = set([c.lower() for c in state.get("clouds", [])])
    all_news = state.get("pending_news", []) or state.get("raw_news", [])
    if clouds:
        all_news = [n for n in all_news if (n.get("source") or "").lower() in clouds]
    if not all_news:
        logger.warning("[ANALYST] No hay noticias para analizar tras filtrar por cloud/source.")
        return {"analyzed_news": []}

    # Lista ampliada de categorías y mapeo español-inglés
    CATEGORIAS_AMPLIADAS = [
        "security", "cost", "architecture", "compliance", "identity", "networking", "storage", "compute", "ai", "devops", "monitoring", "backup", "database", "migration", "updates", "vulnerability", "incident", "policy", "automation", "governance", "marketplace", "support", "eol", "general"
    ]
    MAPEO_ES_EN = {
        "seguridad": "security",
        "coste": "cost",
        "arquitectura": "architecture",
        "cumplimiento": "compliance",
        "identidad": "identity",
        "redes": "networking",
        "almacenamiento": "storage",
        "cómputo": "compute",
        "computo": "compute",
        "ia": "ai",
        "inteligencia artificial": "ai",
        "devops": "devops",
        "monitorización": "monitoring",
        "monitorizacion": "monitoring",
        "copia de seguridad": "backup",
        "backup": "backup",
        "base de datos": "database",
        "migración": "migration",
        "migracion": "migration",
        "actualizaciones": "updates",
        "vulnerabilidad": "vulnerability",
        "incidente": "incident",
        "política": "policy",
        "politica": "policy",
        "automatización": "automation",
        "automatizacion": "automation",
        "gobernanza": "governance",
        "marketplace": "marketplace",
        "soporte": "support",
        "fin de vida": "eol",
        "general": "general"
    }
    # Traducir dinámicamente categorías del prompt
    prompt_cats = [c.lower() for c in state.get("categories", [])]
    mapped_cats = [MAPEO_ES_EN.get(c, c) for c in prompt_cats]
    categories = set(mapped_cats) | set(CATEGORIAS_AMPLIADAS)
    keywords = set([k.lower() for k in state.get("keywords", [])])
    max_to_process = state.get("max_news_to_process") or 30  # Límite MVP por defecto

    def analyze_item(news):
        analysis = {}
        title = news.get("title", "").lower()
        content = news.get("full_content", "").lower() or news.get("body", "").lower()
        # Multi-categoría: todas las categorías que aparecen en título o contenido
        matched_cats = [c for c in categories if c in title or c in content]
        analysis["categories"] = matched_cats if matched_cats else ["general"]
        # Coincidencia de keywords
        kw_matches = [k for k in keywords if k in title or k in content]
        analysis["keywords"] = kw_matches
        # Scoring avanzado
        # 1. Coincidencia de keywords (peso 3)
        # 2. Número de categorías (peso 2)
        # 3. Frescura de la noticia (peso 2)
        # 4. Longitud del contenido (peso 1, penaliza textos muy cortos)
        score = 0
        score += 3 * len(kw_matches)
        score += 2 * len(matched_cats)
        # Frescura: más reciente, más score (máx 2 puntos)
        pub_date = news.get("published_at") or news.get("published_date")
        try:
            pub_dt = parse_date(pub_date)
            if pub_dt:
                days_ago = (datetime.now() - pub_dt).days
                if days_ago <= 1:
                    score += 2
                elif days_ago <= 3:
                    score += 1
        except Exception:
            pass
        # Longitud del contenido
        if len(content) > 400:
            score += 1
        elif len(content) < 100:
            score -= 1
        analysis["relevance_score"] = score
        # Relevancia: relevante si tiene alguna keyword o categoría
        analysis["matches_user_interest"] = bool(kw_matches or matched_cats)
        return analysis

    analyzed_news = []
    for n in all_news:
        analysis = analyze_item(n)
        if analysis["matches_user_interest"]:
            n["analysis"] = analysis
            analyzed_news.append(n)
            # Persistir análisis en BBDD si hay hash
            if n.get("content_hash"):
                try:
                    update_event_analysis(n["content_hash"], analysis)
                except Exception as e:
                    if debug_mode:
                        logger.warning(f"[DEBUG] No se pudo actualizar análisis en BBDD: {e}")

    # Ordenar por score de relevancia descendente y limitar a max_to_process
    analyzed_news.sort(key=lambda x: x["analysis"].get("relevance_score", 0), reverse=True)
    analyzed_news = analyzed_news[:max_to_process]
    logger.info(f"[ANALYST] Noticias analizadas y relevantes: {len(analyzed_news)} (máximo permitido: {max_to_process})")
    return {"analyzed_news": analyzed_news}

