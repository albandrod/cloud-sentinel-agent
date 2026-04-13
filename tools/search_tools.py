import requests
import re
import hashlib
import feedparser
import time
import warnings
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup, GuessedAtParserWarning
from langchain_core.tools import tool
from concurrent.futures import ThreadPoolExecutor, as_completed

_CACHE = {}
_CACHE_TTL = 300  # segundos
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("search_tools")

# Silenciamos avisos de BeautifulSoup para mantener el log limpio
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)

# --- UTILIDADES DE PROCESAMIENTO DINÁMICO ---

def is_within_time_window(published_parsed, days: int = 3) -> bool:
    """Verifica si la entrada está dentro de la ventana de días solicitada."""
    if not published_parsed:
        return True  # Por precaución procesamos si no hay fecha
    
    # Convertir struct_time a objeto datetime UTC
    dt_published = datetime.fromtimestamp(time.mktime(published_parsed), tz=timezone.utc)
    now = datetime.now(timezone.utc)
    return dt_published > (now - timedelta(days=days))

def clean_html_content(html: str) -> str:
    """Limpia el HTML evitando errores de rutas de archivos y avisos innecesarios."""
    if not html or not isinstance(html, str) or len(html.strip()) < 5:
        return ""
    
    # CCOE Guard: Evita parsear strings que parecen rutas o enlaces
    if html.strip().startswith(('http', 'C:', '/', '\\', 'ftp')):
        return html.strip()

    try:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup(["script", "style", "img", "iframe", "figure", "header", "footer", "nav"]):
            el.decompose()
        
        text = soup.get_text(separator=' ')
        return re.sub(r'\s+', ' ', text).strip()
    except Exception:
        return re.sub('<[^<]+?>', '', html).strip()

def generate_hash(text: str, date: str = None) -> str:
    """Genera un identificador único MD5 para control de duplicados."""
    if date:
        return hashlib.md5(f"{text}|{date}".encode('utf-8')).hexdigest()
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# --- CLASES COLECTORAS (MULTI-CLOUD REFORZADAS) ---

def _cache_get(key):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry['ts'] < _CACHE_TTL):
        return entry['data']
    return None

def _cache_set(key, data):
    _CACHE[key] = {'data': data, 'ts': time.time()}

def _validate_news_item(item: Dict) -> Optional[Dict]:
    # Limpieza y validación básica
    title = item.get('title', '').strip()
    link = item.get('link', '').strip()
    body = item.get('body', '').strip()
    content_hash = item.get('content_hash', '').strip()
    if not title or not link or not content_hash:
        return None
    item['title'] = title[:300]
    item['link'] = link
    item['body'] = body
    item['content_hash'] = content_hash
    return item

def _filter_and_paginate(news: List[Dict], search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
    filtered = news
    if search:
        search = search.lower()
        filtered = [n for n in news if search in n.get('title', '').lower() or search in n.get('body', '').lower()]
    start = (page-1)*page_size
    end = start + page_size
    return filtered[start:end]

class AzureCollector:
    URLS = [
    "https://www.microsoft.com/releasecommunications/api/v2/azure/rss",
    "https://status.azure.com/en-us/status/feed/",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureDBSupport",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=azure-ai-foundry-blog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=MicrosoftDefenderCloudBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureSecurityBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=CoreInfrastructureandSecurityBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureNetworkSecurityBlog",
    "https://techcommunity.microsoft.com/t5/s/plugins/custom/microsoft/o365/custom-blog-rss?tid=2251275586151906910&board=AppsonAzureBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureDevCommunityBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=MicrosoftMissionCriticalBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=NonprofitTechies",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=IntegrationsonAzureBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=WindowsServerNewsandBestPractices",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=ITOpsTalkBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=PartnerNews",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureArcBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-security-blog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=MicrosoftMechanicsBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=IntegrationsonAzureBlog",
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzureObservabilityBlog",
    "https://azureweekly.info/rss.xml",
    "https://aztty.azurewebsites.net/rss/updates"
]

    @classmethod
    def fetch_all(cls, days: int = 5, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
        # Cambia el parámetro 'days' aquí para ajustar la ventana de ingestión histórica (por defecto: 5 días)
        cache_key = f"azure_{days}"
        cached = _cache_get(cache_key)
        if cached:
            logger.info("AzureCollector: usando caché.")
            return _filter_and_paginate(cached, search, page, page_size)
        all_news = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml"
        }
        def fetch_url(url):
            try:
                logger.info(f"[AzureCollector] Intentando fetch: {url}")
                response = requests.get(url, headers=headers, timeout=10)
                logger.info(f"[AzureCollector] Respuesta HTTP: {response.status_code} para {url}")
                if response.status_code != 200:
                    logger.error(f"[AzureCollector] Feed {url} status code: {response.status_code}")
                    return []
                feed = feedparser.parse(response.content)
                logger.info(f"[AzureCollector] Feed {url} - {len(feed.entries)} items encontrados.")
                items = []
                for entry in feed.entries:
                    pub_date = entry.get('published', None)
                    pub_parsed = entry.get('published_parsed', None)
                    logger.info(f"[AzureCollector] Feed {url} - Item: '{entry.get('title', '')[:60]}' Fecha: {pub_date} Parsed: {pub_parsed}")
                    if not is_within_time_window(pub_parsed, days=days):
                        logger.info(f"[AzureCollector] Feed {url} - DESCARTADO por fecha: {pub_date}")
                        continue
                    title = entry.get('title', 'Sin título')
                    link = entry.get('link', '')
                    raw_content = entry.content[0].value if 'content' in entry else entry.get('summary', '')
                    body = clean_html_content(raw_content)
                    published_at = entry.get('published', datetime.now(timezone.utc).isoformat())
                    item = {
                        "source": "azure",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body if body else title, published_at),
                        "published_at": published_at,
                        "published_date": datetime.fromtimestamp(time.mktime(pub_parsed)).isoformat() if pub_parsed else None
                    }
                    valid = _validate_news_item(item)
                    if valid:
                        items.append(valid)
                logger.info(f"[AzureCollector] Feed {url} - {len(items)} items válidos tras filtrado.")
                return items
            except Exception as e:
                logger.error(f"[AzureCollector] ERROR en fetch_url para {url}: {type(e).__name__}: {e}", exc_info=True)
                return []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_url, url) for url in cls.URLS]
            for future in as_completed(futures):
                all_news.extend(future.result())
        # Elimina duplicados por hash
        unique = {n['content_hash']: n for n in all_news}
        result = list(unique.values())
        _cache_set(cache_key, result)
        return _filter_and_paginate(result, search, page, page_size)

class AWSCollector:
    URLS = [
    "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    "https://aws.amazon.com/blogs/architecture/feed/",
    "https://aws.amazon.com/blogs/networking-and-content-delivery/feed/",
    "https://aws.amazon.com/blogs/security/feed/",
    "https://aws.amazon.com/blogs/compute/feed/",
    "https://aws.amazon.com/blogs/containers/feed/",
    "https://aws.amazon.com/blogs/database/feed/",
    "https://aws.amazon.com/blogs/storage/feed/",
    "https://aws.amazon.com/blogs/mt/feed/",
    "https://status.aws.amazon.com/rss/all.rss",
    "https://cloudonaut.io/index.xml",
    "https://theburningmonk.com/feed/",
    "https://www.lastweekinaws.com/feed/",
    "https://lucvandonkersgoed.com/feed/",
    "https://www.jeremydaly.com/feed/",
    "https://advancedweb.hu/rss.xml"
]

    @classmethod
    def fetch_all(cls, days: int = 5, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
        # Cambia el parámetro 'days' aquí para ajustar la ventana de ingestión histórica (por defecto: 5 días)
        cache_key = f"aws_{days}"
        cached = _cache_get(cache_key)
        if cached:
            logger.info("AWSCollector: usando caché.")
            return _filter_and_paginate(cached, search, page, page_size)
        all_news = []
        headers = {"User-Agent": "Mozilla/5.0"}
        def fetch_url(url):
            try:
                logger.info(f"[AWSCollector] Intentando fetch: {url}")
                response = requests.get(url, headers=headers, timeout=10)
                logger.info(f"[AWSCollector] Respuesta HTTP: {response.status_code} para {url}")
                if response.status_code != 200:
                    logger.error(f"[AWSCollector] Feed {url} status code: {response.status_code}")
                    return []
                feed = feedparser.parse(response.content)
                logger.info(f"[AWSCollector] Feed {url} - {len(feed.entries)} items encontrados.")
                items = []
                for entry in feed.entries:
                    if not is_within_time_window(entry.get('published_parsed'), days=days):
                        logger.info(f"[AWSCollector] Feed {url} - DESCARTADO por fecha: {entry.get('published', None)}")
                        continue
                    title = entry.get('title', 'Sin título')
                    link = entry.get('link', '')
                    content_list = entry.get('content', [])
                    raw_text = content_list[0].value if content_list else entry.get('summary', "")
                    body = clean_html_content(raw_text)
                    published_at = entry.get('published', datetime.now(timezone.utc).isoformat())
                    item = {
                        "source": "aws",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body if body else title, published_at),
                        "published_at": published_at,
                        "published_date": datetime.fromtimestamp(time.mktime(entry.published_parsed)).isoformat() if entry.get('published_parsed') else None
                    }
                    valid = _validate_news_item(item)
                    if valid:
                        items.append(valid)
                return items
            except Exception as e:
                logger.error(f"[AWSCollector] ERROR en fetch_url para {url}: {type(e).__name__}: {e}", exc_info=True)
                return []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_url, url) for url in cls.URLS]
            for future in as_completed(futures):
                all_news.extend(future.result())
        unique = {n['content_hash']: n for n in all_news}
        result = list(unique.values())
        _cache_set(cache_key, result)
        return _filter_and_paginate(result, search, page, page_size)

class GCPCollector:
    URLS = [
    "https://cloudblog.withgoogle.com/products/gcp/rss/",            # Blog de Productos GCP
    "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/", # IA y ML (Vital)
    "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/", # GKE e Infra
    "https://cloudblog.withgoogle.com/products/databases/rss/",      # Bases de datos
    "https://cloudblog.withgoogle.com/products/identity-security/rss/", # Seguridad e IAM
    "https://cloudblog.withgoogle.com/products/networking/rss/",     # Redes
    "https://cloudblog.withgoogle.com/topics/developers/rss/",       # DevTools
    "https://status.cloud.google.com/en/feed.atom",                  # Incidencias y Status
]

    @classmethod
    def fetch_all(cls, days: int = 5, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
        # Cambia el parámetro 'days' aquí para ajustar la ventana de ingestión histórica (por defecto: 5 días)
        cache_key = f"gcp_{days}"
        cached = _cache_get(cache_key)
        if cached:
            logger.info("GCPCollector: usando caché.")
            return _filter_and_paginate(cached, search, page, page_size)
        all_news = []
        headers = {"User-Agent": "Mozilla/5.0"}
        def fetch_url(url):
            try:
                logger.info(f"[GCPCollector] Intentando fetch: {url}")
                response = requests.get(url, headers=headers, timeout=10)
                logger.info(f"[GCPCollector] Respuesta HTTP: {response.status_code} para {url}")
                if response.status_code != 200:
                    logger.error(f"[GCPCollector] Feed {url} status code: {response.status_code}")
                    return []
                feed = feedparser.parse(response.content)
                logger.info(f"[GCPCollector] Feed {url} - {len(feed.entries)} items encontrados.")
                items = []
                for entry in feed.entries:
                    if not is_within_time_window(entry.get('published_parsed'), days=days):
                        logger.info(f"[GCPCollector] Feed {url} - DESCARTADO por fecha: {entry.get('published', None)}")
                        continue
                    title = entry.get('title', 'Sin título')
                    link = entry.get('link', '')
                    content_list = entry.get('content', [])
                    raw_text = content_list[0].value if content_list else entry.get('summary', "")
                    body = clean_html_content(raw_text)
                    published_at = entry.get('published', datetime.now(timezone.utc).isoformat())
                    item = {
                        "source": "gcp",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body if body else title, published_at),
                        "published_at": published_at,
                        "published_date": datetime.fromtimestamp(time.mktime(entry.published_parsed)).isoformat() if entry.get('published_parsed') else None
                    }
                    valid = _validate_news_item(item)
                    if valid:
                        items.append(valid)
                return items
            except Exception as e:
                logger.error(f"[GCPCollector] ERROR en fetch_url para {url}: {type(e).__name__}: {e}", exc_info=True)
                return []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_url, url) for url in cls.URLS]
            for future in as_completed(futures):
                all_news.extend(future.result())
        unique = {n['content_hash']: n for n in all_news}
        result = list(unique.values())
        _cache_set(cache_key, result)
        return _filter_and_paginate(result, search, page, page_size)

# --- TOOLS EXPORTADAS ---

@tool
def get_azure_updates(days: int = 3, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
    """Consulta novedades de Azure. Soporta días, búsqueda, paginación."""
    return AzureCollector.fetch_all(days=days, search=search, page=page, page_size=page_size)

@tool
def get_aws_updates(days: int = 3, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
    """Consulta novedades de AWS. Soporta días, búsqueda, paginación."""
    return AWSCollector.fetch_all(days=days, search=search, page=page, page_size=page_size)

@tool
def get_gcp_updates(days: int = 3, search: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict]:
    """Consulta novedades de GCP. Soporta días, búsqueda, paginación."""
    return GCPCollector.fetch_all(days=days, search=search, page=page, page_size=page_size)