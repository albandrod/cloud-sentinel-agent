from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from schema.state import AgentState

# --- DEFINICIÓN DE NODOS (Placeholders por ahora) ---

def collector_node(state: AgentState):
    print("--- EJECUTANDO COLLECTOR (Buscando noticias...) ---")
    # Aquí irá la lógica de fetch_rss
    return {"next_step": "analyze"}

def analyst_node(state: AgentState):
    print("--- EJECUTANDO ANALYST (Evaluando impacto...) ---")
    # Aquí irá la lógica de Azure OpenAI (gpt-4o-mini)
    return {"next_step": "report"}

def librarian_node(state: AgentState):
    print("--- EJECUTANDO LIBRARIAN (Guardando en DB...) ---")
    # Aquí irá la lógica de sqlite3
    return {"next_step": "end"}

def writer_node(state: AgentState):
    print("--- EJECUTANDO WRITER (Generando informes para clientes...) ---")
    # Aquí la lógica de generación de informes estratégicos
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
workflow.add_edge("analyst", "writer")
workflow.add_edge("writer", "librarian")
workflow.add_edge("librarian", END)

# 3. Compilamos
app = workflow.compile()