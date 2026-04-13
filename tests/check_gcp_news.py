import sqlite3
conn = sqlite3.connect('cloud_sentinel.db')
cursor = conn.cursor()
cursor.execute("SELECT source, title, published_at FROM events WHERE (source='gcp' OR source='google') AND published_at >= '2026-03-25' ORDER BY published_at DESC;")
rows = cursor.fetchall()
print('Total:', len(rows))
for row in rows:
    print(row)
conn.close()