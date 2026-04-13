import sqlite3
import json
from collections import Counter

DB_PATH = 'cloud_sentinel.db'
CATEGORIAS_AMPLIADAS = [
    "security", "cost", "architecture", "compliance", "identity", "networking", "storage", "compute", "ai", "devops", "monitoring", "backup", "database", "migration", "updates", "vulnerability", "incident", "policy", "automation", "governance", "marketplace", "support", "eol", "general"
]

def recategorize():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, full_content, analysis_json FROM events WHERE is_processed=1')
    rows = cursor.fetchall()
    print(f"Total noticias a recategorizar: {len(rows)}")
    updated = 0
    for row in rows:
        id_, title, content, analysis_json = row
        title = (title or '').lower()
        content = (content or '').lower()
        matched_cats = [c for c in CATEGORIAS_AMPLIADAS if c in title or c in content]
        if matched_cats:
            category = matched_cats if len(matched_cats) > 1 else matched_cats[0]
        else:
            category = "general"
        # Actualizar analysis_json
        try:
            analysis = json.loads(analysis_json) if analysis_json else {}
        except Exception:
            analysis = {}
        analysis["category"] = category
        new_analysis_json = json.dumps(analysis, ensure_ascii=False)
        cursor.execute('UPDATE events SET analysis_json=? WHERE id=?', (new_analysis_json, id_))
        updated += 1
        if updated % 100 == 0:
            print(f"Actualizadas {updated} noticias...")
    conn.commit()
    print(f"Recategorización completada. Total actualizadas: {updated}")
    conn.close()

if __name__ == '__main__':
    recategorize()
