import os
import datetime
import re
import warnings
import logging
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schema.state import AgentState
from fpdf import FPDF
try:
    import markdown2
except ImportError:
    markdown2 = None

warnings.filterwarnings("ignore", category=UserWarning)

# =========================================================
# UTILS DE RENDERIZADO (FIX CRÍTICO ESPACIO HORIZONTAL)
# =========================================================

def hard_wrap_text(text: str, max_chars: int = 40) -> str:
    """Trocea cadenas sin espacios (URLs largas) para que quepan en el PDF."""
    if not text:
        return ""
    words = text.split(' ')
    new_words = []
    for word in words:
        # Si la palabra es demasiado larga, la cortamos en fragmentos de max_chars
        while len(word) > max_chars:
            new_words.append(word[:max_chars])
            word = word[max_chars:]
        if word:
            new_words.append(word)
    return " ".join(new_words)

def clean_latin1(text: str) -> str:
    if not text: return ""
    replacements = {
        '\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '*', '\u2026': '...',
        '\u20ac': 'EUR', '\u2122': '(TM)', '\u00ae': '(R)', '\u00a9': '(C)'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = text.replace('**', '').replace('__', '').replace('`', "'")
    return text.encode('latin-1', 'replace').decode('latin-1')

# =========================================================
# MOTOR PDF REFORZADO
# =========================================================

def save_as_pdf(markdown_text: str, filename: str, resumen_stats: dict = None):
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        logo_path = "./assets/seidor-logo.png"
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=85, y=10, w=40)
            pdf.ln(35)
        else:
            pdf.ln(10)

        # Enriquecimiento visual: tabla resumen
        if resumen_stats:
            pdf.set_font("Arial", 'B', 12)
            pdf.set_text_color(0, 59, 92)
            pdf.cell(0, 10, "Resumen de noticias por nube", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.set_text_color(40, 40, 40)
            for k, v in resumen_stats.items():
                pdf.cell(0, 8, f"{k}: {v}", ln=True)
            pdf.ln(5)

        for line in markdown_text.split('\n'):
            line = line.strip()
            if not line or any(x in line for x in ["<div", "img src", "---"]): continue
            
            # Aplicamos un wrap muy estricto para evitar el error de "horizontal space"
            line_safe = clean_latin1(hard_wrap_text(line, max_chars=50))

            if line.startswith('#'):
                level = line.count('#')
                pdf.set_font("Arial", 'B', 14 if level == 1 else 12)
                pdf.set_text_color(0, 59, 92)
                pdf.ln(2)
                pdf.multi_cell(0, 7, line_safe.replace('#', '').strip())
                pdf.ln(1)
            elif "http" in line.lower() or "ref" in line.lower():
                pdf.set_font("Courier", 'I', 8)
                pdf.set_text_color(0, 80, 150)
                pdf.multi_cell(0, 4, line_safe)
            else:
                pdf.set_font("Arial", size=10)
                pdf.set_text_color(40, 40, 40)
                pdf.multi_cell(0, 5, line_safe)

        pdf.output(filename)
        print(f"✅ PDF generado con éxito: {filename}")
    except Exception as e:
        print(f"❌ Error al generar PDF: {e}")

# =========================================================
# WRITER NODE (MULTI-CLOUD DINÁMICO)
# =========================================================

def writer_node(state: AgentState) -> Dict[str, Any]:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("writer")
    logger.info("--- WRITER AGENT: MODO MULTI-CLOUD DINÁMICO ---")
    debug_mode = os.getenv("DEBUG_MODE", "0") == "1" or state.get("debug_mode")


    # 1. Recuperar noticias analizadas y aplicar limpieza/filtros avanzados
    all_news = state.get("analyzed_news", [])
    if not all_news:
        logger.warning("📭 No hay noticias analizadas para redactar.")
        if debug_mode:
            logger.info("[DEBUG] No se encontraron noticias analizadas en el estado.")
        return {"next_step": "end"}

    # --- FILTRO AVANZADO Y LIMPIEZA ---
    # 1. Eliminar duplicados por (title, published_at) o (title, link) o hash si existe
    seen = set()
    filtered_news = []
    for n in all_news:
        key = n.get("content_hash") or (n.get("title",""), n.get("published_at","")) or (n.get("title",""), n.get("link",""))
        if key in seen:
            if debug_mode:
                logger.info(f"[DEBUG] Noticia descartada por duplicada: {n.get('title','')} | {n.get('published_at','')} | {n.get('link','')}")
            continue
        seen.add(key)
        filtered_news.append(n)

    # 2. Asegura que el análisis esté completo (analysis_json o analysis válido)
    def is_valid_analysis(n):
        analysis = n.get("analysis") or n.get("analysis_json")
        if not analysis or analysis == "null":
            return False
        if isinstance(analysis, str):
            try:
                import json
                analysis = json.loads(analysis)
            except Exception:
                return False
        return bool(analysis)
    filtered_news_valid = []
    for n in filtered_news:
        if is_valid_analysis(n):
            filtered_news_valid.append(n)
        elif debug_mode:
            logger.info(f"[DEBUG] Noticia descartada por análisis incompleto: {n.get('title','')} | {n.get('published_at','')} | {n.get('link','')}")
    filtered_news = filtered_news_valid

    # 3. Filtros avanzados por prompt (nube, categoría, keywords, fechas)
    clouds = set([c.lower() for c in state.get("clouds", [])])
    categories = set([c.lower() for c in state.get("categories", [])])
    keywords = set([k.lower() for k in state.get("keywords", [])])
    from_date = state.get("from_date")
    to_date = state.get("to_date")
    def match_filters(n):
        # Cloud/source (AND)
        if clouds:
            src = (n.get("source") or "").lower()
            if not any(c in src for c in clouds):
                return False

        # OR para categorías y keywords
        cat_match = False
        kw_match = False
        if categories:
            cat = (n.get("category") or n.get("categories") or "").lower()
            cat_match = any(c in cat for c in categories)
        if keywords:
            text = (n.get("title","") + " " + n.get("full_content","")).lower()
            kw_match = any(k in text for k in keywords)

        # Si hay categorías o keywords, debe coincidir al menos una
        if categories or keywords:
            if not (cat_match or kw_match):
                return False

        # Fechas
        pub_date = n.get("published_at")
        if from_date and pub_date and pub_date < from_date:
            return False
        if to_date and pub_date and pub_date > to_date:
            return False
        return True
    filtered_news_final = []
    for n in filtered_news:
        if match_filters(n):
            filtered_news_final.append(n)
        elif debug_mode:
            logger.info(f"[DEBUG] Noticia descartada por filtros avanzados: {n.get('title','')} | {n.get('published_at','')} | {n.get('link','')}")
    filtered_news = filtered_news_final

    # 4. Ordenar por fecha descendente y aplicar límite N más recientes
    def parse_date_safe(d):
        try:
            return datetime.datetime.strptime(d[:10], "%Y-%m-%d")
        except Exception:
            return datetime.datetime.min

    filtered_news.sort(key=lambda n: parse_date_safe(n.get("published_at", "")), reverse=True)

    # Límite N: configurable por estado, por defecto 30
    max_news = state.get("max_news_to_process") or state.get("limit") or 30
    filtered_news = filtered_news[:max_news]
    all_news = filtered_news

    logger.info(f"[WRITER] Noticias tras limpieza y filtros: {len(filtered_news)}")
    if debug_mode:
        logger.info(f"[DEBUG] Total noticias descartadas: {len(all_news) - len(filtered_news)}")
    if not filtered_news:
        logger.warning("📭 No hay noticias válidas tras filtros avanzados.")
        if debug_mode:
            logger.info("[DEBUG] Todas las noticias fueron descartadas tras aplicar filtros y validaciones.")
        return {"next_step": "end"}
    all_news = filtered_news

    # Recuperar el prompt original del usuario para el resumen
    user_prompt = state.get("user_instructions") or state.get("messages", [{}])[-1].get("content", "")

    # Internacionalización y personalización: usar SIEMPRE lo que viene del orquestador
    idioma = state.get("lang", "es")
    tipo_label = state.get("report_type", "Ejecutivo")
    # Normalizar para nombre de archivo
    tipo_label_file = tipo_label.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    # Labels multidioma
    TITLES = {
        "es": {
            "ejecutivo": "Informe Ejecutivo Multi-Cloud",
            "técnico": "Informe Técnico Multi-Cloud",
            "tecnico": "Informe Técnico Multi-Cloud",
            "resumen": "Resumen Multi-Cloud",
            "completo": "Informe Completo Multi-Cloud",
            "personalizado": "Informe Personalizado Multi-Cloud",
            "default": "Informe Multi-Cloud de Novedades"
        },
        "en": {
            "ejecutivo": "Executive Multi-Cloud Report",
            "técnico": "Technical Multi-Cloud Report",
            "tecnico": "Technical Multi-Cloud Report",
            "resumen": "Multi-Cloud Summary",
            "completo": "Full Multi-Cloud Report",
            "personalizado": "Custom Multi-Cloud Report",
            "default": "Multi-Cloud News Report"
        }
    }
    RESUMEN_LABEL = {"es": "Resumen", "en": "Summary"}
    GENERADO_LABEL = {
        "es": "Generado por Cloud Sentinel - Inteligencia Seidor",
        "en": "Generated by Cloud Sentinel - Seidor Intelligence"
    }
    import unicodedata
    tlabel = tipo_label.lower()
    tlabel = unicodedata.normalize('NFKD', tlabel).encode('ascii', 'ignore').decode('ascii')
    titulo = TITLES.get(idioma, TITLES["es"]).get(tlabel, TITLES.get(idioma, TITLES["es"])['default'])
    resumen_label = RESUMEN_LABEL.get(idioma, "Resumen")
    generado_label = GENERADO_LABEL.get(idioma, GENERADO_LABEL["es"])

    # Contadores para resumen visual
    count_azure = sum(1 for n in all_news if "azure" in str(n).lower())
    count_aws = sum(1 for n in all_news if "aws" in str(n).lower())
    count_gcp = sum(1 for n in all_news if "gcp" in str(n).lower() or "google" in str(n).lower())
    resumen_stats = {"Azure": count_azure, "AWS": count_aws, "GCP": count_gcp}
    logger.info(f"📊 Total noticias: {len(all_news)} (Azure: {count_azure}, AWS: {count_aws}, GCP: {count_gcp})")

    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0
    )

    # 2. Procesamiento por lotes (Batch de 5) y procesamiento paralelo
    batch_size = 5
    report_body = ""

    # PROMPTS DIFERENCIADOS SEGÚN TIPO DE INFORME Y IDIOMA
    def get_prompt(tipo, lang):
        if lang == "en":
            if tipo == "técnico" or tipo == "tecnico":
                return "You are a Senior Cloud Architect. Write a DETAILED TECHNICAL report for specialists.\n- Include technical details, context, implications, and recommendations.\n- Use precise and professional language.\n- For each news item, include: context, technical impact, possible actions, and references.\n- Format: ### [CLOUD] - [Title]\nContext: ...\nImpact: ...\nRecommendations: ...\nref: ...\nThe report must be in English."
            elif tipo == "ejecutivo":
                return "You are a cloud consultant. Write an EXECUTIVE summary report for managers.\n- Be clear, concise, and business-oriented.\n- For each news item, summarize the impact and business relevance.\n- Format: ### [CLOUD] - [Title]\nExecutive summary: ...\nref: ...\nThe report must be in English."
            elif tipo == "resumen":
                return "You are a cloud analyst. Write a very brief SUMMARY with only headlines and key points.\n- Omit technical details, only the essentials.\n- Format: - [CLOUD] [Title]: key point. ref: ...\nThe report must be in English."
            elif tipo == "completo":
                return "You are a cloud expert. Write a FULL report with maximum detail.\n- Include context, analysis, technical and business implications, and recommendations.\n- For each news item, structure: context, analysis, impact, recommendations, references.\n- Format: ### [CLOUD] - [Title]\nContext: ...\nAnalysis: ...\nImpact: ...\nRecommendations: ...\nref: ...\nThe report must be in English."
            else:
                return "You are a Cloud Solutions Architect.\nWrite the news keeping their original provider (Azure, AWS, or GCP) or the cloud they refer to, even if the user specifies several clouds.\nGroup or clearly identify which cloud each update belongs to.\nRULES:\n1. Do NOT omit any news from the batch.\n2. INCLUDE the URL as 'ref:'.\n3. Use professional and structured language.\n4. Format: ### [CLOUD] - [Title]\nThe report must be in English.\nReport type: {tipo_label}"
        else:
            if tipo == "técnico" or tipo == "tecnico":
                return "Eres un Arquitecto Cloud Senior. Redacta un informe TÉCNICO detallado para especialistas.\n- Incluye detalles técnicos, contexto, implicaciones y recomendaciones.\n- Usa lenguaje preciso y profesional.\n- Para cada noticia, incluye: contexto, impacto técnico, posibles acciones y referencias.\n- Formato: ### [NUBE] - [Título]\nContexto: ...\nImpacto: ...\nRecomendaciones: ...\nref: ...\nEl informe debe estar en español."
            elif tipo == "ejecutivo":
                return "Eres un consultor cloud. Redacta un informe EJECUTIVO resumido para directivos.\n- Sé claro, conciso y orientado a negocio.\n- Para cada noticia, resume el impacto y la relevancia en términos de negocio.\n- Formato: ### [NUBE] - [Título]\nResumen ejecutivo: ...\nref: ...\nEl informe debe estar en español."
            elif tipo == "resumen":
                return "Eres un analista cloud. Redacta un RESUMEN muy breve solo con titulares y puntos clave.\n- Omite detalles técnicos, solo lo esencial.\n- Formato: - [NUBE] [Título]: punto clave. ref: ...\nEl informe debe estar en español."
            elif tipo == "completo":
                return "Eres un experto cloud. Redacta un informe COMPLETO con máximo detalle.\n- Incluye contexto, análisis, implicaciones técnicas y de negocio, y recomendaciones.\n- Para cada noticia, estructura: contexto, análisis, impacto, recomendaciones, referencias.\n- Formato: ### [NUBE] - [Título]\nContexto: ...\nAnálisis: ...\nImpacto: ...\nRecomendaciones: ...\nref: ...\nEl informe debe estar en español."
            else:
                return "Eres un Cloud Solutions Architect.\nDebes redactar las noticias manteniendo su proveedor original (Azure, AWS o GCP) o la nube a la que se refieran, incluso si el usuario especifica varias nubes en su petición.\nAgrupa o identifica claramente a qué nube pertenece cada actualización.\nREGLAS:\n1. NO omitas ninguna noticia del lote.\n2. INCLUYE la URL como 'ref:'.\n3. Usa un lenguaje profesional y estructurado.\n4. Formato: ### [NUBE] - [Título]\nEl informe debe estar en español.\nTipo de informe: {tipo_label}"

    system_prompt = get_prompt(tlabel, idioma)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Redacta estas noticias:\n{lote}")
    ])
    chain = prompt | llm

    def redactar_lote(lote):
        try:
            response = chain.invoke({"lote": str(lote)})
            text = response.content
            # Post-procesar: reemplazar [NUBE] por el proveedor real en cada noticia del lote
            # Suponemos que cada noticia tiene 'source' y 'title'
            for noticia in lote:
                # Detectar proveedor (Azure, AWS, GCP, Google)
                fuente = (noticia.get('source') or '').strip()
                fuente_norm = fuente.lower()
                if 'azure' in fuente_norm:
                    nube = 'Azure'
                elif 'aws' in fuente_norm:
                    nube = 'AWS'
                elif 'gcp' in fuente_norm or 'google' in fuente_norm:
                    nube = 'GCP'
                else:
                    nube = fuente if fuente else 'Multi-Cloud'
                # Reemplazar solo la primera ocurrencia de [NUBE] en el bloque correspondiente al título
                titulo = noticia.get('title', '').strip()
                # Buscar el patrón de la noticia en el texto generado
                # Formato esperado: ### [NUBE] - {titulo}
                pattern = re.escape('### [NUBE] - ') + re.escape(titulo)
                replacement = f'### {nube} - {titulo}'
                text = re.sub(pattern, replacement, text, count=1)
            return text + "\n\n"
        except Exception as e:
            logger.error(f"  ⚠️ Error en bloque: {e}")
            return ""

    lotes = [all_news[i:i+batch_size] for i in range(0, len(all_news), batch_size)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(redactar_lote, lote) for lote in lotes]
        for future in as_completed(futures):
            report_body += future.result()

    # 3. Ensamblado final
    fecha_hoy = str(datetime.date.today())
    # Usar el prompt del usuario como resumen, sin plantilla genérica
    # Eliminar enriquecimiento y sección de resumen
    full_markdown = f"""# {titulo} ({tipo_label})
**Fecha:** {fecha_hoy}

{report_body}

---
*{generado_label}*"""

    os.makedirs("reports", exist_ok=True)
    filename_base = f"reports/informe_{tipo_label_file}_{fecha_hoy}"

    # Guardar Markdown
    try:
        with open(f"{filename_base}.md", "w", encoding="utf-8") as f:
            f.write(full_markdown)
        logger.info(f"✅ Markdown generado: {filename_base}.md")
    except Exception as e:
        logger.error(f"❌ Error al guardar Markdown: {e}")

    # PDF desactivado temporalmente por errores de espacio horizontal
    # try:
    #     save_as_pdf(full_markdown, f"{filename_base}.pdf", resumen_stats=resumen_stats)
    # except Exception as e:
    #     logger.error(f"❌ Error al guardar PDF: {e}")

    # Soporte para HTML si markdown2 está disponible
    if markdown2:
        try:
            html = markdown2.markdown(full_markdown)
            with open(f"{filename_base}.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"✅ HTML generado: {filename_base}.html")
        except Exception as e:
            logger.error(f"❌ Error al guardar HTML: {e}")

    return {"next_step": "end"}