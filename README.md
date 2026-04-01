# cloud-sentinel-agent

Sistema automatizado para la vigilancia, análisis y generación de informes sobre novedades críticas en servicios cloud (Azure, AWS, GCP).

## Objetivo

Automatizar la obtención, filtrado, análisis y redacción de informes profesionales sobre noticias relevantes de la nube, facilitando la monitorización de cambios técnicos, alertas de seguridad, novedades de arquitectura, costes y fin de vida (EOL) de servicios.

## Arquitectura

- **Orquestador principal (main.py)**: Controla el flujo de trabajo, coordinando la obtención, análisis y generación de informes.
- **Agentes (skills):**
  - **Collector Agent (collector.py)**: Recolecta noticias de fuentes oficiales, filtra duplicados y almacena solo las nuevas.
  - **Analyst Agent (analyst.py)**: Analiza y puntúa la relevancia técnica de cada noticia usando IA (Azure OpenAI) y reglas personalizables.
  - **Writer Agent (writer.py)**: Genera informes en diferentes formatos (ejecutivo, técnico, alerta) a partir de plantillas y LLM, redactando en Markdown.
- **Herramientas (tools):**
  - **db_tools.py**: Gestión de la base de datos local (SQLite), control de duplicados, almacenamiento y recuperación de eventos.
  - **search_tools.py**: Colectores específicos para Azure, AWS y GCP, normalización de noticias y generación de hashes únicos.
- **Esquema de estado (state.py)**: Define la estructura de datos compartida entre agentes.

## Flujo de Automatización

1. **Obtención de noticias**: El Collector consulta feeds oficiales, filtra duplicados y almacena solo las noticias nuevas.
2. **Análisis de IA**: El Analyst clasifica y puntúa cada noticia según criterios técnicos y preferencias del usuario.
3. **Generación de informes**: El Writer permite elegir el formato y genera un informe profesional en Markdown.
4. **Persistencia**: Los informes se guardan como archivos `.md` y las noticias procesadas se marcan en la base de datos.

## Funcionalidades

- Modularidad basada en agentes y herramientas reutilizables.
- Integración con Azure OpenAI para análisis semántico y redacción avanzada.
- Plantillas de informe personalizables para distintos perfiles (ejecutivo, técnico, alerta).
- Persistencia local y control de duplicados mediante hashes.
- Fácil extensión para nuevos feeds o criterios de análisis.
- Interactividad mínima: el usuario solo elige el formato del informe.

## Ejemplo de Uso

1. Ejecuta el orquestador principal:
   ```
   python main.py
   ```
2. El sistema verifica si hay noticias pendientes; si no, lanza el Collector.
3. Las noticias nuevas pasan al Analyst, que las filtra y puntúa.
4. El usuario elige el tipo de informe (ejecutivo/técnico/alerta).
5. El Writer genera y guarda el informe en Markdown en la carpeta de salida.

## Requisitos

- Python 3.8+
- Dependencias listadas en requirements.txt
- Acceso a Azure OpenAI (para análisis y redacción avanzada)

Instalación de dependencias:
```
pip install -r requirements.txt
```

## Estructura del Proyecto

- main.py — Orquestador principal
- collector.py — Agente recolector de noticias
- analyst.py — Agente analista (IA)
- writer.py — Agente generador de informes
- db_tools.py — Herramientas de base de datos
- search_tools.py — Colectores de feeds cloud
- state.py — Esquema de datos compartido

## Personalización

- Puedes modificar las plantillas de informes en el Writer Agent para adaptarlas a tus necesidades.
- Es posible añadir nuevos feeds o criterios de análisis editando los colectores en `search_tools.py` y las reglas en el Analyst Agent.

## Créditos

Desarrollado por albandrod.