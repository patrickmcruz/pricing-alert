import sqlite3

conn = sqlite3.connect('data/prices.db')
cur = conn.cursor()

print("Prices for Mercado Livre:")
cur.execute(
    """
    SELECT po.* FROM price_observations po
    JOIN store_listings sl ON sl.id = po.store_listing_id
    JOIN stores s ON s.id = sl.store_id
    WHERE s.slug = 'mercado-livre'
    """
)
print(cur.fetchall())

print("\nTarget URLs for Mercado Livre:")
cur.execute(
    """
    SELECT sl.* FROM store_listings sl
    JOIN stores s ON s.id = sl.store_id
    WHERE s.slug = 'mercado-livre'
    """
)
print(cur.fetchall())
