from typing import Dict, Any
from schema.state import AgentState
from tools.search_tools import get_azure_updates, get_aws_updates, get_gcp_updates
from tools.db_tools import filter_new_hashes, save_raw_news

def collector_node(state: AgentState) -> Dict[str, Any]:
    print("--- 🕵️‍♂️ INICIANDO COLLECTOR AGENT ---")

    # 1. Recolectar de todas las fuentes (Ejecutamos las tools directamente)
    print("Obteniendo noticias de Azure, AWS y GCP...")
    
    # Al ser @tools de Langchain, se ejecutan pasándoles un diccionario vacío si no requieren argumentos
    azure_news = get_azure_updates.invoke({})
    aws_news = get_aws_updates.invoke({})
    gcp_news = get_gcp_updates.invoke({})

    all_news = azure_news + aws_news + gcp_news
    
    if not all_news:
        print("No se encontraron noticias en las fuentes.")
        return {"next_step": "end"} # Cortamos el grafo aquí

    # 2. Filtrar lo que ya hemos procesado antes
    print(f"Total de noticias crudas obtenidas: {len(all_news)}")
    all_hashes = [news["content_hash"] for news in all_news]
    
    # Preguntamos a la base de datos cuáles son nuevos
    new_hashes = filter_new_hashes.invoke({"hashes": all_hashes})

    if not new_hashes:
        print("🛑 No hay noticias nuevas. Todas están ya en la base de datos.")
        # Evitamos despertar al Analyst y gastar tokens
        return {"next_step": "end", "raw_news": []} 

    # 3. Extraer solo los diccionarios de las noticias 100% nuevas
    new_news_items = [news for news in all_news if news["content_hash"] in new_hashes]
    print(f"🟢 Noticias 100% nuevas detectadas: {len(new_news_items)}")

    # 4. Guardar en la base de datos en estado "pendiente" (is_processed = 0)
    save_raw_news.invoke({"news_list": new_news_items})
    print("💾 Noticias nuevas guardadas en la base de datos local.")

    # 5. Pasarle el relevo al Analista
    # Actualizamos el AgentState con las noticias limpias y le decimos a LangGraph que avance
    return {
        "raw_news": new_news_items,
        "next_step": "analyze"
    }