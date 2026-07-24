import asyncio
import os
import sys
import asyncpg

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings

def get_allowed_patterns() -> list[str]:
    """Dynamically loads target GPU patterns from config.toml (settings.default_gpus)."""
    patterns = []
    for item in settings.default_gpus:
        item_clean = item.strip().lower()
        patterns.append(item_clean)
        # Also add no-space variant (e.g. 'rtx 5070 ti' -> '5070ti')
        patterns.append(item_clean.replace(" ", ""))
        # Also add core model string (e.g. 'rtx 5070' -> '5070')
        parts = item_clean.split()
        for p in parts:
            if p not in ("rtx", "rx", "gtx"):
                patterns.append(p)
    return list(set(patterns))


NON_GPU_WORDS = [
    "computador", "pc gamer", "pc completo", "pc elite", "pc pichau", "pc mancer",
    "pc workstation", "pc ecovision", "xtreme pc", "notebook", "laptop",
    "processador", "kit upgrade", "placa mãe", "placa mae", "memória", "memoria",
    "fonte", "gabinete", "ssd", "watercooler", "cooler", "teclado", "headset",
    "monitor", "waterblock", "cabo riser", "extensor"
]


def is_allowed_keyword(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    for forbidden in NON_GPU_WORDS:
        if forbidden in lower:
            return False
    allowed_patterns = get_allowed_patterns()
    for allowed in allowed_patterns:
        if allowed in lower:
            return True
    return False


def is_non_gpu_title(title: str) -> bool:
    if not title:
        return False
    lower = title.lower()
    for forbidden in NON_GPU_WORDS:
        if forbidden in lower:
            return True
    return False


async def purge_database(dsn: str, db_name: str, dry_run: bool = False):
    print(f"\n--- Processing Database: {db_name} (dsn: {dsn}) ---")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"Skipping {db_name}: Could not connect ({e})")
        return

    try:
        # 1. Inspect target_urls
        target_urls = await conn.fetch("SELECT id, store_name, search_keyword, product_url, product_title FROM target_urls")
        target_urls_to_delete = [
            row["id"] for row in target_urls
            if is_non_gpu_title(row["product_title"] or "") or not is_allowed_keyword(row["search_keyword"])
        ]
        print(f"target_urls: {len(target_urls_to_delete)} / {len(target_urls)} flagged for deletion")

        # 2. Inspect listings
        listings = await conn.fetch("""
            SELECT l.id, l.search_keyword, l.product_url, l.product_title, p.specs->>'chipset' AS chipset, p.name AS product_name
            FROM listings l
            JOIN products p ON p.id = l.product_id
        """)
        listings_to_delete = [
            row["id"] for row in listings
            if is_non_gpu_title(row["product_title"] or "") or
               is_non_gpu_title(row["product_name"] or "") or
               not is_allowed_keyword(row["search_keyword"])
        ]
        print(f"listings: {len(listings_to_delete)} / {len(listings)} flagged for deletion")

        # 3. Inspect products
        products = await conn.fetch("""
            SELECT p.id, p.name, p.specs->>'chipset' AS chipset
            FROM products p
        """)
        products_to_delete = [
            row["id"] for row in products
            if not (is_allowed_keyword(row["name"] or "") or is_allowed_keyword(row["chipset"] or ""))
        ]
        print(f"products: {len(products_to_delete)} / {len(products)} flagged for deletion")

        if dry_run:
            print("DRY RUN mode: No changes committed.")
            return

        # Perform actual deletion in FK-safe order
        async with conn.transaction():
            if target_urls_to_delete:
                await conn.execute("DELETE FROM target_urls WHERE id = ANY($1::uuid[])", target_urls_to_delete)
                print(f"Deleted {len(target_urls_to_delete)} target_urls.")

            if listings_to_delete:
                # Delete price_observations FK'd to listings
                res_po = await conn.execute("DELETE FROM price_observations WHERE listing_id = ANY($1::uuid[])", listings_to_delete)
                print(f"Deleted price_observations: {res_po}")

                # Delete listing_runs FK'd to listings
                res_lr = await conn.execute("DELETE FROM listing_runs WHERE listing_id = ANY($1::uuid[])", listings_to_delete)
                print(f"Deleted listing_runs: {res_lr}")

                # Delete listings
                res_l = await conn.execute("DELETE FROM listings WHERE id = ANY($1::uuid[])", listings_to_delete)
                print(f"Deleted listings: {res_l}")

            if products_to_delete:
                # Any orphan products
                res_p = await conn.execute("DELETE FROM products WHERE id = ANY($1::uuid[]) AND id NOT IN (SELECT product_id FROM listings)", products_to_delete)
                print(f"Deleted products: {res_p}")

        print(f"Successfully purged non-target GPUs from {db_name}!")
    finally:
        await conn.close()


async def main():
    dry_run = "--dry-run" in sys.argv
    base_dsn = settings.db_dsn

    # Databases to purge
    db_names = ["pricing", "pricing_dev", "pricing_staging", "pricing_test"]
    for db_name in db_names:
        # Reconstruct DSN for target db_name
        user = settings.db_user
        password = settings.db_password
        host = settings.db_host
        port = settings.db_port
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
        await purge_database(dsn, db_name, dry_run=dry_run)

if __name__ == "__main__":
    asyncio.run(main())
