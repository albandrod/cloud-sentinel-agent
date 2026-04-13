import sqlite3
from datetime import datetime

DB_PATH = "cloud_sentinel.db"

def noticias_hoy():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hoy = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT published_at, title, source FROM events WHERE published_at = ? ORDER BY published_at DESC LIMIT 20", (hoy,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"No hay noticias con fecha de hoy ({hoy}) en la base de datos.")
    else:
        print(f"Noticias con fecha de hoy ({hoy}):")
        for r in rows:
            print(f"- [{r[0]}] {r[2]}: {r[1]}")

if __name__ == "__main__":
    noticias_hoy()
