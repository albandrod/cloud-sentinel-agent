import sqlite3
from datetime import datetime
import re
try:
    from dateutil import parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

DB_PATH = "cloud_sentinel.db"

def robust_clean_date(date_str):
    if not date_str:
        return datetime.now().strftime('%Y-%m-%d')
    # Si ya es YYYY-MM-DD
    if re.match(r"\d{4}-\d{2}-\d{2}", str(date_str)):
        return str(date_str)[:10]
    # Usa dateutil si está disponible
    if HAS_DATEUTIL:
        try:
            dt = parser.parse(str(date_str), fuzzy=True, default=datetime.now())
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # Fallback manual
    for fmt in ["%a, %d %b", "%a, %d %B", "%d %b %Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(str(date_str), fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            continue
    return datetime.now().strftime('%Y-%m-%d')

def migrate_all_dates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, published_at FROM events")
    rows = cursor.fetchall()
    updates = []
    failed = []
    for row in rows:
        id_, date_str = row
        new_date = robust_clean_date(date_str)
        if new_date != date_str:
            updates.append((new_date, id_))
        if not new_date or new_date == datetime.now().strftime('%Y-%m-%d'):
            failed.append((id_, date_str))
    print(f"Se actualizarán {len(updates)} fechas...")
    for new_date, id_ in updates:
        cursor.execute("UPDATE events SET published_at = ? WHERE id = ?", (new_date, id_))
    conn.commit()
    conn.close()
    print("Migración completada.")
    if failed:
        print("No se pudieron convertir las siguientes fechas:")
        for id_, date_str in failed:
            print(f"ID {id_}: {date_str}")

if __name__ == "__main__":
    migrate_all_dates()
