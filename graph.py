import os
import json
import logging
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from schema.state import AgentState
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graph")

STATE_FILE = "workflow_state.json"
MAX_RETRIES = 2

def save_state(state: AgentState):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, default=str)
        logger.info("Estado del workflow guardado.")
    except Exception as e:
        logger.error(f"Error guardando estado: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info("Estado del workflow restaurado.")
            return state
        except Exception as e:
            logger.error(f"Error cargando estado: {e}")
    return None

def with_retries(node_func):
    def wrapper(state: AgentState):
        for attempt in range(1, MAX_RETRIES+1):
            try:
                logger.info(f"Ejecutando {node_func.__name__} (intento {attempt})")
                result = node_func(state)
                save_state(state)
                return result
            except Exception as e:
                logger.error(f"Error en {node_func.__name__} (intento {attempt}): {e}")
                time.sleep(1)
        logger.error(f"Fallo permanente en {node_func.__name__}")
        return {"next_step": "end"}
    return wrapper

# --- DEFINICIÓN DE NODOS (con logging, errores, bifurcaciones) ---

@with_retries
def collector_node(state: AgentState):
    logger.info("--- EJECUTANDO COLLECTOR (Buscando noticias...) ---")
    # Aquí irá la lógica de fetch_rss
    # Ejemplo de bifurcación dinámica:
    if state.get("skip_analysis"):
        return {"next_step": "writer"}
    return {"next_step": "analyst"}

@with_retries
def analyst_node(state: AgentState):
    logger.info("--- EJECUTANDO ANALYST (Evaluando impacto...) ---")
    # Aquí irá la lógica de Azure OpenAI (gpt-4o-mini)
    # Ejemplo de bifurcación dinámica:
    if not state.get("analyzed_news"):
        logger.warning("No hay noticias analizadas, saltando a writer.")
        return {"next_step": "writer"}
    return {"next_step": "writer"}

@with_retries
def librarian_node(state: AgentState):
    logger.info("--- EJECUTANDO LIBRARIAN (Guardando en DB...) ---")
    # Aquí irá la lógica de sqlite3
    return {"next_step": "end"}

@with_retries
def writer_node(state: AgentState):
    logger.info("--- EJECUTANDO WRITER (Generando informes para clientes...) ---")
    # Aquí la lógica de generación de informes estratégicos
    # Ejemplo de bifurcación dinámica:
    if state.get("only_save"):
        return {"next_step": "librarian"}
    return {"next_step": "archive"}

# --- CONSTRUCCIÓN DEL GRAFO ---

workflow = StateGraph(AgentState)

# 1. Añadimos los nodos
workflow.add_node("collector", collector_node)
workflow.add_node("analyst", analyst_node)
workflow.add_node("writer", writer_node)
workflow.add_node("librarian", librarian_node)

# 2. Definimos el flujo (Edges)
workflow.set_entry_point("collector")
workflow.add_edge("collector", "analyst")
workflow.add_edge("collector", "writer")  # bifurcación dinámica
workflow.add_edge("analyst", "writer")
workflow.add_edge("writer", "librarian")
workflow.add_edge("librarian", END)

# 3. Compilamos
app = workflow.compile()