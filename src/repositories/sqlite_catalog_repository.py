import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from src.core.catalog import Brand, ChipMaker, GpuChipset, GpuModel, ResolvedGpuModel
from src.db.schema import connect
from src.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)


class SQLiteCatalogRepository(CatalogRepository):
    """SQLite implementation of CatalogRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_or_create_brand(self, name: str) -> Brand:
        name = name.strip()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name FROM brands WHERE LOWER(name) = LOWER(?)", (name,)
            )
            row = await cursor.fetchone()
            if row:
                return Brand(id=row[0], name=row[1])

            brand = Brand(id=str(uuid4()), name=name)
            await db.execute(
                "INSERT INTO brands (id, name, created_at) VALUES (?, ?, ?)",
                (brand.id, brand.name, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
            logger.info("Created brand %s (%s)", brand.name, brand.id)
            return brand

    async def get_or_create_chipset(
        self, name: str, chip_maker: ChipMaker = ChipMaker.UNKNOWN
    ) -> GpuChipset:
        name = name.strip()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name, chip_maker FROM chipsets WHERE LOWER(name) = LOWER(?)",
                (name,),
            )
            row = await cursor.fetchone()
            if row:
                return GpuChipset(id=row[0], name=row[1], chip_maker=ChipMaker(row[2]))

            chipset = GpuChipset(id=str(uuid4()), name=name, chip_maker=chip_maker)
            await db.execute(
                "INSERT INTO chipsets (id, name, chip_maker, created_at) VALUES (?, ?, ?, ?)",
                (
                    chipset.id,
                    chipset.name,
                    chipset.chip_maker.value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            logger.info("Created GPU chipset %s (%s)", chipset.name, chipset.id)
            return chipset

    async def get_or_create_gpu_model(
        self, brand_id: str, chipset_id: str, model_name: str
    ) -> GpuModel:
        model_name = model_name.strip()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT id, brand_id, chipset_id, model_name FROM gpu_models
                WHERE brand_id = ? AND chipset_id = ? AND LOWER(model_name) = LOWER(?)
                """,
                (brand_id, chipset_id, model_name),
            )
            row = await cursor.fetchone()
            if row:
                return GpuModel(id=row[0], brand_id=row[1], chipset_id=row[2], model_name=row[3])

            gpu_model = GpuModel(
                id=str(uuid4()), brand_id=brand_id, chipset_id=chipset_id, model_name=model_name
            )
            await db.execute(
                "INSERT INTO gpu_models (id, brand_id, chipset_id, model_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    gpu_model.id,
                    gpu_model.brand_id,
                    gpu_model.chipset_id,
                    gpu_model.model_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            logger.info("Created GPU model %s (%s)", gpu_model.model_name, gpu_model.id)
            return gpu_model

    async def get_gpu_model(self, gpu_model_id: str) -> Optional[GpuModel]:
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, brand_id, chipset_id, model_name FROM gpu_models WHERE id = ?",
                (gpu_model_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return GpuModel(id=row[0], brand_id=row[1], chipset_id=row[2], model_name=row[3])

    async def list_brands(self) -> List[Brand]:
        async with connect(self.db_path) as db:
            cursor = await db.execute("SELECT id, name FROM brands ORDER BY name")
            rows = await cursor.fetchall()
            return [Brand(id=row[0], name=row[1]) for row in rows]

    async def list_chipsets(self) -> List[GpuChipset]:
        async with connect(self.db_path) as db:
            cursor = await db.execute("SELECT id, name, chip_maker FROM chipsets ORDER BY name")
            rows = await cursor.fetchall()
            return [GpuChipset(id=row[0], name=row[1], chip_maker=ChipMaker(row[2])) for row in rows]

    async def list_gpu_models_resolved(self) -> List[ResolvedGpuModel]:
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT gm.id, b.name, c.name, gm.model_name
                FROM gpu_models gm
                JOIN brands b ON b.id = gm.brand_id
                JOIN chipsets c ON c.id = gm.chipset_id
                """
            )
            rows = await cursor.fetchall()
            return [
                ResolvedGpuModel(id=row[0], brand_name=row[1], chipset_name=row[2], model_name=row[3])
                for row in rows
            ]
