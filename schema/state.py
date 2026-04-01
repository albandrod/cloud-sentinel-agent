from typing import Annotated, List, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Lista de mensajes (historial de lo que dicen los agentes)
    messages: Annotated[list, add_messages]
    
    # Datos de negocio
    raw_news: List[dict]         # Lo que encuentra el Collector
    analyzed_news: List[dict]    # Lo que procesa el Analyst
    reports: List[dict]          # Lo que escribe el Writer
    
    # Control de flujo
    next_step: str               # Para decidir a dónde ir después