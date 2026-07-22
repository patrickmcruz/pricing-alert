import asyncio
import logging
from src.core.config import settings
from src.db.schema import connect
from src.core.title_parser import TitleParserRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NON_GPU_KEYWORDS = [
    "pc gamer", "computador", "workstation", "kit upgrade",
    "controle", "fonte", "gabinete", "cooler", "processador", "memoria ram"
]

async def main():
    dsn = settings.db_dsn
    logger.info("Connecting to database DSN: %s", dsn)

    reclassified_count = 0
    deactivated_count = 0

    async with connect(dsn) as db:
        rows = await db.fetch(
            """
            SELECT l.id, l.search_keyword, l.product_title, l.product_url, p.id AS product_id
            FROM listings l
            JOIN products p ON p.id = l.product_id
            WHERE l.is_active = true
            """
        )
        logger.info("Auditing %d active listings...", len(rows))

        for row in rows:
            listing_id = row["id"]
            old_keyword = row["search_keyword"]
            title = row["product_title"]
            title_lower = title.lower()

            # 1. Deactivate non-standalone GPU listings (PC Gamer prebuilts, kits, accessories)
            if any(non_gpu in title_lower for non_gpu in NON_GPU_KEYWORDS):
                await db.execute(
                    "UPDATE listings SET is_active = false, updated_at = NOW() WHERE id = $1",
                    listing_id
                )
                logger.info("Deactivated non-GPU listing [%s]: %s", old_keyword, title[:80])
                deactivated_count += 1
                continue

            # 2. Parse true chipset from title
            parsed = TitleParserRegistry.parse_gpu(title)
            if parsed.chipset:
                true_keyword = parsed.chipset.lower()
                if true_keyword != old_keyword:
                    # Update listings search_keyword to true_keyword
                    await db.execute(
                        "UPDATE listings SET search_keyword = $1, updated_at = NOW() WHERE id = $2",
                        true_keyword, listing_id
                    )
                    # Update products specs chipset
                    await db.execute(
                        """
                        UPDATE products
                        SET specs = jsonb_set(COALESCE(specs, '{}'::jsonb), '{chipset}', $1::jsonb)
                        WHERE id = $2
                        """,
                        f'"{parsed.chipset}"', row["product_id"]
                    )
                    logger.info("Reclassified listing [%s -> %s]: %s", old_keyword, true_keyword, title[:80])
                    reclassified_count += 1

    logger.info("==================================================")
    logger.info("CLEANUP COMPLETE: %d reclassified, %d deactivated non-GPU items.", reclassified_count, deactivated_count)
    logger.info("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
