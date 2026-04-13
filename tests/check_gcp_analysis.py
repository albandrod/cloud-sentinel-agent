import sqlite3
import json
conn = sqlite3.connect('cloud_sentinel.db')
cursor = conn.cursor()
cursor.execute("SELECT title, analysis_json FROM events WHERE source='gcp' AND published_at >= '2026-03-25' ORDER BY published_at DESC LIMIT 20;")
rows = cursor.fetchall()
print('Total:', len(rows))
for title, analysis_json in rows:
    try:
        analysis = json.loads(analysis_json) if analysis_json else None
        print(f'TITLE: {title}\nCATEGORY: {analysis.get("category") if analysis else None}\nMATCHES: {analysis.get("matches_user_interest") if analysis else None}\nSCORE: {analysis.get("relevance_score") if analysis else None}\n')
    except Exception as e:
        print(f'TITLE: {title}\nERROR: {e}\n')
conn.close()