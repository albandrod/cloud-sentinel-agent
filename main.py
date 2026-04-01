import os
from dotenv import load_dotenv

# 1. Cargar configuración
load_dotenv(override=True)

from tools.db_tools import init_db, get_unprocessed_events, get_analyzed_events
from agents.collector import collector_node
from agents.analyst import analyst_node
from agents.writer import writer_node

def run_sentinel_orchestrator():
    """
    Orquestador Cloud Sentinel:
    Inyecta nuevas noticias -> Analiza el backlog pendiente -> Genera reporte del histórico.
    """
    print("\n" + "="*50)
    print("🛰️  CLOUD SENTINEL: SISTEMA DE INTELIGENCIA")
    print("="*50)
    
    init_db()
    import sqlite3
    conn = sqlite3.connect("cloud_sentinel.db") # Asegúrate de que el nombre sea el tuyo
    conn.execute("UPDATE events SET is_processed = 1 WHERE published_at < date('now', '-7 days') AND is_processed = 0")
    conn.commit()
    conn.close()
    print("🧹 Backlog antiguo limpiado. Centrándonos en la última semana...")

    # --- CONFIGURACIÓN DE FILTRADO ---
    user_prompt = input("\n🔍 ¿Qué quieres monitorizar hoy? (ej: Azure Seguridad, AWS Costes...): ")
    if not user_prompt:
        user_prompt = "Prioriza noticias de Azure sobre costes, seguridad y EOL."

    # Paso 1: Obtener noticias nuevas para procesar (Backlog)
    print("\n[1/3] Verificando noticias pendientes de análisis...")
    pending = get_unprocessed_events.invoke({"limit": 15}) # Mantenemos el paracaídas de gasto
    
    if not pending:
        print("📭 No hay noticias nuevas. Ejecutando Collector...")
        collector_node({"raw_news": []})
        pending = get_unprocessed_events.invoke({"limit": 15})

    # Paso 2: Análisis y Enriquecimiento (Analyst Agent)
    # Enviamos solo las pendientes para no gastar tokens en las que ya tienen JSON
    print(f"[2/3] El Analyst está procesando {len(pending)} noticias nuevas...")
    
    state = {
        "raw_news": pending, 
        "analyzed_news": [], 
        "user_instructions": user_prompt 
    }
    
    # El Analyst analiza las 15 nuevas y las guarda en la DB
    analyst_node(state)

    # --- AMPLIACIÓN DEL SCOPE PARA EL REPORTE ---
    # Ahora que la DB está actualizada, recuperamos un scope mayor (ej: las últimas 50 ya analizadas)
    # Esto permite que el Writer use noticias de ejecuciones anteriores.
    print(f"📈 Ampliando scope: Recuperando histórico de noticias analizadas...")
    full_history = get_analyzed_events.invoke({"limit": 50}) 

    # Pasamos todo el historial al Analyst de nuevo (pero esta vez solo para FILTRAR por el prompt del usuario)
    # Como ya tienen 'analysis_json', el Analyst no gastará tokens de LLM, solo aplicará el filtro de relevancia.
    state_for_filtering = {
        "raw_news": full_history,
        "analyzed_news": [],
        "user_instructions": user_prompt
    }
    
    final_state = analyst_node(state_for_filtering)

    # Paso 3: Generación de Reporte (Writer Agent)
    if final_state.get("analyzed_news"):
        num_noticias = len(final_state['analyzed_news'])
        print(f"\n✅ Se han encontrado {num_noticias} noticias relevantes en el histórico reciente.")
        writer_node(final_state)
    else:
        print("\n⚠️  No se han encontrado noticias relevantes en el scope actual.")

if __name__ == "__main__":
    run_sentinel_orchestrator()