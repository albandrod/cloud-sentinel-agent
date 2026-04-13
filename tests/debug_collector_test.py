import sys
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
from tools import search_tools

def print_news_summary(label, news):
    print(f"\n--- {label} ---")
    print(f"Total noticias: {len(news)}")
    for i, item in enumerate(news[:5]):
        print(f"{i+1}. {item.get('title', '')[:120]}")
    if len(news) > 5:
        print(f"... y {len(news)-5} más")

def main():
    print("Probando recolección directa de feeds (Azure, AWS, GCP)...\n")
    # Azure
    azure_news = search_tools.AzureCollector.fetch_all(days=3)
    print_news_summary("Azure", azure_news)
    # AWS
    aws_news = search_tools.AWSCollector.fetch_all(days=3)
    print_news_summary("AWS", aws_news)
    # GCP
    gcp_news = search_tools.GCPCollector.fetch_all(days=3)
    print_news_summary("GCP", gcp_news)

if __name__ == "__main__":
    main()
