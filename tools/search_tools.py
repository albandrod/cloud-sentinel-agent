import requests
import re
import time
import hashlib
import feedparser
from typing import List, Dict
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from langchain_core.tools import tool

# --- UTILIDADES COMUNES ---

def clean_html_content(html: str) -> str:
    """Limpia el HTML y devuelve texto plano legible."""
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "img", "iframe", "figure", "header", "footer"]):
        el.decompose()
    text = soup.get_text(separator=' ')
    return re.sub(r'\s+', ' ', text).strip()

def generate_hash(text: str) -> str:
    """Genera un hash único basado en el contenido para evitar duplicados."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# --- CLASES COLECTORAS ---

class AzureCollector:
    URLS = [
    "https://www.microsoft.com/releasecommunications/api/v2/azure/rss",
    "https://github.com/Azure/AKS/releases.atom",
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
    def fetch_all(cls) -> List[Dict]:
        all_news = []
        headers = {"User-Agent": "cloud-sentinel-agent/3.0"}
        for url in cls.URLS:
            try:
                r = requests.get(url, timeout=20, headers=headers)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "xml")
                items = soup.find_all(["item", "entry"])
                for item in items:
                    title = item.find("title").get_text() if item.find("title") else "N/A"
                    link_tag = item.find("link")
                    link = (link_tag.get("href") or link_tag.get_text()) if link_tag else ""
                    desc_tag = item.find(["description", "summary", "content"])
                    body = clean_html_content(desc_tag.get_text() if desc_tag else "")
                    
                    all_news.append({
                        "source": "azure",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body),
                        "published_at": datetime.now(timezone.utc).isoformat()
                    })
            except Exception as e:
                print(f"Error en Azure {url}: {e}")
        return all_news

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
    "https://aws.amazon.com/blogs/opensource/feed/",
    "https://status.aws.amazon.com/rss/all.rss",
    "https://cloudonaut.io/index.xml",
    "https://theburningmonk.com/feed/",
    "https://www.lastweekinaws.com/feed/",
    "https://github.com/aws/aws-cdk/releases.atom",
    "https://github.com/boto/boto3/releases.atom",
    "https://lucvandonkersgoed.com/feed/",
    "https://github.com/aws/aws-cli/releases.atom",
    "https://www.jeremydaly.com/feed/",
    "https://advancedweb.hu/rss.xml"
]

    @classmethod
    def fetch_all(cls) -> List[Dict]:
        all_news = []
        for url in cls.URLS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title = entry.get('title', 'Sin título')
                    link = entry.get('link', '')
                    content_list = entry.get('content', [])
                    raw_text = content_list[0].value if content_list else entry.get('summary', "")
                    body = clean_html_content(raw_text)
                    
                    all_news.append({
                        "source": "aws",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body),
                        "published_at": datetime.now(timezone.utc).isoformat()
                    })
            except Exception as e:
                print(f"Error en AWS {url}: {e}")
        return all_news

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
    def fetch_all(cls) -> List[Dict]:
        all_news = []
        for url in cls.URLS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    title = entry.get('title', 'Sin título')
                    link = entry.get('link', '')
                    content_list = entry.get('content', [])
                    raw_text = content_list[0].value if content_list else entry.get('summary', "")
                    body = clean_html_content(raw_text)
                    
                    all_news.append({
                        "source": "gcp",
                        "title": title[:300],
                        "link": link,
                        "body": body,
                        "content_hash": generate_hash(body),
                        "published_at": datetime.now(timezone.utc).isoformat()
                    })
            except Exception as e:
                print(f"Error en GCP {url}: {e}")
        return all_news

# --- TOOLS PARA EL AGENTE (EXPOSED) ---

@tool
def get_azure_updates() -> List[Dict]:
    """Consulta feeds oficiales de Azure. Devuelve noticias con hash de contenido."""
    return AzureCollector.fetch_all()

@tool
def get_aws_updates() -> List[Dict]:
    """Consulta feeds oficiales de AWS. Devuelve noticias con hash de contenido."""
    return AWSCollector.fetch_all()

@tool
def get_gcp_updates() -> List[Dict]:
    """Consulta feeds oficiales de GCP. Devuelve noticias con hash de contenido."""
    return GCPCollector.fetch_all()