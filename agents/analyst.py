import json
import os
from typing import Dict, Any, List
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schema.state import AgentState
from tools.db_tools import update_event_analysis

def analyst_node(state: AgentState) -> Dict[str, Any]:
    print("\n--- 🧠 INICIANDO ANALYST AGENT (Enriquecimiento y Filtrado) ---")
    
    user_instr = state.get("user_instructions", "Analiza la relevancia técnica general.")
    
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not all([deployment, api_version, endpoint, api_key]):
        print("❌ ERROR: Faltan variables de configuración en el .env")
        return {"next_step": "end", "analyzed_news": []}

    try:
        llm = AzureChatOpenAI(
            azure_deployment=deployment,
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
            temperature=0
        )
    except Exception as e:
        print(f"❌ Error al inicializar Azure OpenAI: {e}")
        return {"next_step": "end", "analyzed_news": []}

    # Escapamos con doble llave {{ }} para el JSON literal
    system_prompt = f"""Eres un Arquitecto Senior de Soluciones Cloud experto en AWS, Azure y GCP. 
    Analiza la noticia y clasifícala según su impacto técnico real.

    PRIORIDADES GENERALES:
    - CRÍTICA: Cambios de precio, EOL (End of Life), Seguridad.
    - ALTA: Nuevas regiones, GA de servicios clave.
    
    INTERÉS ESPECÍFICO DEL USUARIO (MÁXIMA PRIORIDAD):
    "{user_instr}"
    
    Si la noticia coincide con el interés del usuario, pon matches_user_interest: true y relevance_score: 10.
    
    IMPORTANTE: Si la noticia es solo un cambio de versión de software o SDK (ej: v2.4.1) sin un impacto funcional o de seguridad descrito, asígnale un relevance_score de 1 y marca matches_user_interest: false.

    Debes responder ÚNICAMENTE en formato JSON plano con esta estructura:
    {{{{
        "relevance_score": (int 1-10),
        "matches_user_interest": (boolean),
        "category": "Security" | "Cost" | "Architecture" | "EOL" | "General",
        "technical_summary": "Resumen técnico de 1 frase",
        "is_critical": (boolean),
        "services_affected": ["Servicio"]
    }}}}"""

    # Definimos el template usando marcadores {fuente} y {contenido}
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "PROVEEDOR: {fuente}\nCONTENIDO: {contenido}")
    ])

    news_to_process = state.get("raw_news", [])
    analyzed_results = []

    for item in news_to_process:
        if item.get('analysis_json') and item['analysis_json'] != "null":
            print(f"-> Usando análisis existente para: {item['title'][:50]}...")
            try:
                analysis = json.loads(item['analysis_json'])
            except:
                analysis = None
        else:
            analysis = None

        if not analysis:
            print(f"-> Analizando noticia (Nueva): {item['title'][:50]}...")
            try:
                # PASO CLAVE: Pasamos las variables en el invoke para evitar conflictos de llaves {}
                response = llm.invoke(prompt_template.format_messages(
                    fuente=item.get('source', 'Unknown'),
                    contenido=item.get('full_content', 'No content available')
                ))
                
                content = response.content.strip().replace("```json", "").replace("```", "")
                analysis = json.loads(content)
                
                # Persistencia en DB
                update_event_analysis.invoke({
                    "content_hash": item['content_hash'],
                    "analysis": analysis
                })
            except Exception as e:
                print(f"❌ Error analizando: {e}")
                continue

        # Filtrado para el Writer
        if analysis.get("matches_user_interest") or analysis.get("relevance_score", 0) >= 7:
            analyzed_results.append({
                "title": item['title'],
                "link": item['link'],
                "source": item['source'],
                "analysis": analysis
            })

    return {
        "analyzed_news": analyzed_results,
        "next_step": "write" if analyzed_results else "end"
    }