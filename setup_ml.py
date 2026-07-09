import asyncio
import sqlite3

async def main():
    conn = sqlite3.connect('data/prices.db')
    cur = conn.cursor()
    
    url = "https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb-gddr7-dlss-ray-tracing-vcg507012tfxpb1-o/p/MLB53508354"
    store = "mercado-livre"
    keyword = "rtx 5070"
    brand = "PNY"
    model = "rtx 5070"
    title = "Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc"
    
    # Check if exists
    cur.execute("SELECT 1 FROM target_urls WHERE product_url = ?", (url,))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO target_urls (product_url, store_name, search_keyword, brand, model, product_title)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url, store, keyword, brand, model, title))
        conn.commit()
        print("URL inserted into target_urls.")
    else:
        print("URL already exists in target_urls.")

    # Let's also try to fetch the HTML to create our fixture
    # We will use httpx
    import urllib.request
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            import os
            os.makedirs("tests/fixtures", exist_ok=True)
            with open("tests/fixtures/mercadolivre.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("HTML fixture saved.")
    except Exception as e:
        print(f"Error fetching HTML: {e}")

if __name__ == "__main__":
    asyncio.run(main())
