import sqlite3
from datetime import datetime

def print_recent_news(db_path='cloud_sentinel.db', limit=20):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    print(f"Most recent {limit} news in DB:")
    print("-")
    cur.execute("SELECT published_at, title, source FROM events ORDER BY published_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    for row in rows:
        print(f"{row[0]} | {row[2]} | {row[1][:100]}")
    conn.close()

if __name__ == "__main__":
    print_recent_news()
