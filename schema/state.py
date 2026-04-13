from typing import Annotated, Any, Dict, List, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # --- HISTORIAL ---
    # Lista de mensajes (historial de lo que dicen los agentes)
    messages: Annotated[list, add_messages]
    
    # --- DATOS DE NEGOCIO ---
    raw_news: List[Dict[str, Any]]      # Noticias brutas de la DB
    analyzed_news: List[Dict[str, Any]] # Noticias con el JSON de la IA + source + link
    reports: List[dict]                 # Metadatos de los informes generados
    
    # --- INTELIGENCIA DINÁMICA (NUEVO) ---
    # Guardamos qué nubes (Azure, AWS, GCP) y qué tiempo (72h, 7d, etc.) se han detectado
    filters: Dict[str, Any]             # Ej: {"clouds": ["azure", "aws"], "days": 7}
    user_intent: str                    # La petición original limpia para que los agentes la consulten
    
    # --- CONTROL DE FLUJO ---
    next_step: str                      # Para decidir a dónde ir después
    inventory_count: Dict[str, int]     # Para el log: {"azure": 102, "aws": 90, "gcp": 6}