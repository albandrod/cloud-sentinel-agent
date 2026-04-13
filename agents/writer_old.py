import os
import datetime
import re
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schema.state import AgentState
import pdfkit
from markdown2 import markdown
from fpdf import FPDF

# --- MISMO DICCIONARIO DE TEMPLATES QUE YA TIENES ---
TEMPLATES = {
    "ejecutivo": """# 📊 CLOUD SENTINEL: RESUMEN EJECUTIVO\n**Fecha:** {{fecha}}\n...""",
    "tecnico": """# 🛠️ CLOUD SENTINEL: REPORTE TÉCNICO\n**Fecha:** {{fecha}}\n...""",
    "alerta": """# 🚨 CLOUD SENTINEL: ALERTA\n**ESTADO:** CRÍTICO\n..."""
}

def writer_node(state: AgentState) -> Dict[str, Any]:
    print("\n--- ✍️  WRITER AGENT: GENERANDO REPORTE ---")
    analyzed_news = state.get("analyzed_news", [])
    
    if not analyzed_news:
        print("📭 No hay noticias filtradas para redactar.")
        return {"next_step": "end"}

    print("\n[1] Ejecutivo [2] Técnico [3] Alerta")
    opcion = input("Selecciona formato (1/2/3): ")
    tipo = {"1": "ejecutivo", "2": "tecnico", "3": "alerta"}.get(opcion, "ejecutivo")
    template_text = TEMPLATES.get(tipo, TEMPLATES["ejecutivo"])

    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0.3
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un Redactor Senior Cloud. Tu tarea es rellenar la PLANTILLA proporcionada usando los DATOS adjuntos. Idioma: Español."),
        ("user", "PLANTILLA:\n{plantilla}\n\nDATOS:\n{datos}\n\nFECHA:\n{fecha}")
    ])

    try:
        chain = prompt | llm
        response = chain.invoke({
            "plantilla": template_text,
            "datos": str(analyzed_news),
            "fecha": str(datetime.date.today())
        })
        
        reporte_md = response.content
        
        # 1. Guardar Markdown
        filename_base = f"informe_{tipo}_{datetime.date.today()}"
        with open(f"{filename_base}.md", "w", encoding="utf-8") as f:
            f.write(reporte_md)
        print(f"✅ Markdown guardado: {filename_base}.md")

        # 2. Generar PDF
        save_as_pdf(reporte_md, f"{filename_base}.pdf")
        
    except Exception as e:
        print(f"❌ Error en el Writer: {e}")

    return {"next_step": "end"}

def save_as_pdf(markdown_text: str, filename: str):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Intentamos usar una fuente estándar
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "CLOUD SENTINEL: REPORT", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=11)

        # --- LIMPIEZA DE EMOJIS Y CARACTERES ESPECIALES ---
        # Esta regex elimina emojis para que el PDF no explote
        clean_text = re.sub(r'[^\x00-\x7F]+', '', markdown_text) 
        # También quitamos los símbolos de Markdown para que quede limpio
        clean_text = clean_text.replace("#", "").replace("*", "").replace("`", "")

        pdf.multi_cell(0, 10, clean_text)
        
        pdf_name = filename.replace(".md", ".pdf")
        pdf.output(pdf_name)
        print(f"📄 PDF generado con éxito (Sin emojis): {pdf_name}")
        
    except Exception as e:
        print(f"⚠️ Error al generar PDF portable: {e}")