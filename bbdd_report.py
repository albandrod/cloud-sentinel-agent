import sqlite3
import json
from collections import Counter
import matplotlib.pyplot as plt

DB_PATH = 'cloud_sentinel.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Total de noticias
    total = cursor.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    print(f'Total de noticias: {total}')

    # Noticias procesadas y sin procesar
    processed = cursor.execute('SELECT COUNT(*) FROM events WHERE is_processed=1').fetchone()[0]
    unprocessed = cursor.execute('SELECT COUNT(*) FROM events WHERE is_processed=0').fetchone()[0]
    print(f'Procesadas: {processed} | Sin procesar: {unprocessed}')

    # Categorías únicas (de analysis_json)
    cursor.execute('SELECT analysis_json FROM events WHERE analysis_json IS NOT NULL')
    cats = []
    for (aj,) in cursor.fetchall():
        try:
            data = json.loads(aj)
            cat = data.get('categories') or data.get('category')
            if isinstance(cat, list):
                cats.extend(cat)
            elif cat:
                cats.append(cat)
        except Exception:
            continue
    cat_counter = Counter(cats)
    print(f'Categorías únicas: {list(cat_counter.keys())}')
    print(f'Ranking categorías: {cat_counter.most_common(10)}')

    # Si el usuario pide 'novedades', mostrar las 20 noticias más recientes
    prompt_categoria = input("\nIntroduce una categoría para filtrar (puedes separar varias con coma, o 'novedades' para ver las últimas noticias, ENTER para saltar): ").strip().lower()
    if prompt_categoria == 'novedades':
        cursor.execute('SELECT title, published_at, source FROM events ORDER BY published_at DESC LIMIT 20')
        rows = cursor.fetchall()
        print("\n=== Últimas 20 novedades (sin filtrar por categoría) ===")
        for row in rows:
            print(f"- [{row[2]}] {row[0]} ({row[1]})")
    elif prompt_categoria:
        import re
        # Permite separar por coma, punto y coma, barra, barra vertical, espacio, slash, etc.
        categorias = [c.strip() for c in re.split(r'[ ,;|/\\]+', prompt_categoria) if c.strip()]
        cursor.execute('SELECT title, published_at, source, analysis_json FROM events WHERE analysis_json IS NOT NULL')
        count = 0
        print(f"\n=== Noticias con categoría {'/'.join(categorias)} ===")
        for title, published_at, source, aj in cursor.fetchall():
            try:
                data = json.loads(aj)
                cat = data.get('categories') or data.get('category')
                catlist = [c.lower() for c in cat] if isinstance(cat, list) else [cat.lower()] if isinstance(cat, str) else []
                if any(c in catlist for c in categorias):
                    print(f"- [{source}] {title} ({published_at})")
                    count += 1
            except Exception:
                continue
        if count == 0:
            print("No hay noticias con esas categorías.")

    # Ejemplos de prompts
    print("\n\nEjemplos de uso:")
    print("- Para ver novedades recientes: escribe 'novedades' cuando se te pida la categoría.")
    print("- Para ver solo noticias de seguridad: escribe 'security'.")
    print("- Para ver solo noticias de IA: escribe 'ai'.")
    print("- Para ver noticias de seguridad o IA: escribe 'security,ai'.")
    print("- Si escribes una categoría que no existe, verás un mensaje de que no hay noticias.")

    # Fuentes únicas
    cursor.execute('SELECT DISTINCT source FROM events')
    sources = [row[0] for row in cursor.fetchall()]
    print(f'Fuentes únicas: {sources}')

    # Noticias por día
    cursor.execute('SELECT published_at FROM events')
    days = [row[0] for row in cursor.fetchall() if row[0]]
    day_counter = Counter(days)
    print(f'Fechas más activas: {day_counter.most_common(5)}')

    # Gráficos
    plt.figure(figsize=(10,4))
    plt.bar(cat_counter.keys(), cat_counter.values())
    plt.title('Noticias por categoría')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('noticias_por_categoria.png')
    print('Gráfico guardado como noticias_por_categoria.png')

    plt.figure(figsize=(10,4))
    top_days = dict(day_counter.most_common(15))
    plt.bar(top_days.keys(), top_days.values())
    plt.title('Noticias por día (top 15)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('noticias_por_dia.png')
    print('Gráfico guardado como noticias_por_dia.png')

    conn.close()

if __name__ == '__main__':
    main()
