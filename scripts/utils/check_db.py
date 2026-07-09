import sqlite3

conn = sqlite3.connect('data/prices.db')
cur = conn.cursor()

print("Prices for Mercado Livre:")
cur.execute("SELECT * FROM prices WHERE store_name='mercado-livre'")
print(cur.fetchall())

print("\nTarget URLs for Mercado Livre:")
cur.execute("SELECT * FROM target_urls WHERE store_name='mercado-livre'")
print(cur.fetchall())
