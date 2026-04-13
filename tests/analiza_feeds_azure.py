import feedparser
import requests
from datetime import datetime, timezone, timedelta
import time

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

def is_today(published_parsed):
    if not published_parsed:
        return False
    dt = datetime.fromtimestamp(time.mktime(published_parsed), tz=timezone.utc)
    now = datetime.now(timezone.utc)
    return dt.date() == now.date()

def main():
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in URLS:
        print(f"\n---\nFeed: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"  ERROR: status {resp.status_code}")
                continue
            feed = feedparser.parse(resp.content)
            print(f"  Total items: {len(feed.entries)}")
            found_today = 0
            for entry in feed.entries:
                pub = entry.get('published', None)
                pub_parsed = entry.get('published_parsed', None)
                title = entry.get('title', '')
                if is_today(pub_parsed):
                    found_today += 1
                    print(f"    [HOY] {pub} | {title[:80]}")
                else:
                    print(f"    [NO]  {pub} | {title[:80]}")
            print(f"  Noticias de hoy: {found_today}")
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    main()
