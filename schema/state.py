from typing import Annotated, Any, Dict, List, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Lista de mensajes (historial de lo que dicen los agentes)
    messages: Annotated[list, add_messages]
    
    # Datos de negocio
    raw_news: List[Dict[str, Any]]      # Noticias brutas de la DB
    analyzed_news: List[Dict[str, Any]] # Noticias con el JSON de la IA + source + link
    reports: List[dict]          # Lo que escribe el Writer
    
    # Control de flujo
    next_step: str               # Para decidir a dónde ir después