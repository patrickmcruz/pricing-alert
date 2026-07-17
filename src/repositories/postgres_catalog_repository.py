import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import uuid4

from src.core.catalog import Categoria, Marca, Produto, ResolvedProduto
from src.db.schema import connect
from src.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)


class PostgresCatalogRepository(CatalogRepository):
    """PostgreSQL implementation of CatalogRepository, using the same database as prices."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def get_or_create_categoria(
        self, nome: str, slug: str, parent_id: Optional[str] = None
    ) -> Categoria:
        slug = slug.strip().lower()
        async with connect(self.dsn) as db:
            row = await db.fetchrow("SELECT id, name, slug, parent_id FROM categories WHERE slug = $1", slug)
            if row:
                return self._row_to_categoria(row)

            categoria = Categoria(id=str(uuid4()), nome=nome.strip(), slug=slug, parent_id=parent_id)
            await db.execute(
                "INSERT INTO categories (id, name, slug, parent_id, created_at) VALUES ($1, $2, $3, $4, $5)",
                categoria.id, categoria.nome, categoria.slug, categoria.parent_id,
                datetime.now(timezone.utc),
            )
            logger.info("Created categoria %s (%s)", categoria.nome, categoria.id)
            return categoria

    async def get_or_create_marca(self, nome: str) -> Marca:
        nome = nome.strip()
        async with connect(self.dsn) as db:
            row = await db.fetchrow("SELECT id, name FROM brands WHERE LOWER(name) = LOWER($1)", nome)
            if row:
                return Marca(id=str(row["id"]), nome=row["name"])

            marca = Marca(id=str(uuid4()), nome=nome)
            await db.execute(
                "INSERT INTO brands (id, name, created_at) VALUES ($1, $2, $3)",
                marca.id, marca.nome, datetime.now(timezone.utc),
            )
            logger.info("Created marca %s (%s)", marca.nome, marca.id)
            return marca

    async def get_or_create_produto(
        self,
        marca_id: str,
        categoria_id: str,
        nome: str,
        specs: Optional[dict[str, Any]] = None,
    ) -> Produto:
        nome = nome.strip()
        specs = specs or {}
        chipset = specs.get("chipset")
        async with connect(self.dsn) as db:
            row = await db.fetchrow(
                """
                SELECT id, brand_id, category_id, name, gtin, specs FROM products
                WHERE brand_id = $1 AND category_id = $2 AND LOWER(name) = LOWER($3)
                  AND (specs->>'chipset') IS NOT DISTINCT FROM $4
                """,
                marca_id, categoria_id, nome, chipset,
            )
            if row:
                return self._row_to_produto(row)

            produto = Produto(
                id=str(uuid4()), marca_id=marca_id, categoria_id=categoria_id, nome=nome, specs=specs
            )
            await db.execute(
                "INSERT INTO products (id, brand_id, category_id, name, gtin, specs, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                produto.id, produto.marca_id, produto.categoria_id, produto.nome, produto.gtin,
                produto.specs, datetime.now(timezone.utc),
            )
            logger.info("Created produto %s (%s)", produto.nome, produto.id)
            return produto

    async def get_produto(self, produto_id: str) -> Optional[Produto]:
        async with connect(self.dsn) as db:
            row = await db.fetchrow(
                "SELECT id, brand_id, category_id, name, gtin, specs FROM products WHERE id = $1",
                produto_id,
            )
            return self._row_to_produto(row) if row else None

    async def list_marcas(self) -> List[Marca]:
        async with connect(self.dsn) as db:
            rows = await db.fetch("SELECT id, name FROM brands ORDER BY name")
            return [Marca(id=str(row["id"]), nome=row["name"]) for row in rows]

    async def list_categorias(self) -> List[Categoria]:
        async with connect(self.dsn) as db:
            rows = await db.fetch("SELECT id, name, slug, parent_id FROM categories ORDER BY name")
            return [self._row_to_categoria(row) for row in rows]

    async def list_produtos_resolved(self, categoria_slug: Optional[str] = None) -> List[ResolvedProduto]:
        query = """
            SELECT p.id, b.name AS marca_nome, c.name AS categoria_nome, p.name, p.specs
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
        """
        async with connect(self.dsn) as db:
            if categoria_slug:
                rows = await db.fetch(query + " WHERE c.slug = $1", categoria_slug)
            else:
                rows = await db.fetch(query)
            return [
                ResolvedProduto(
                    id=str(row["id"]),
                    marca_nome=row["marca_nome"],
                    categoria_nome=row["categoria_nome"],
                    nome=row["name"],
                    specs=row["specs"],
                )
                for row in rows
            ]

    @staticmethod
    def _row_to_categoria(row) -> Categoria:
        return Categoria(
            id=str(row["id"]), nome=row["name"], slug=row["slug"],
            parent_id=str(row["parent_id"]) if row["parent_id"] else None,
        )

    @staticmethod
    def _row_to_produto(row) -> Produto:
        return Produto(
            id=str(row["id"]), marca_id=str(row["brand_id"]), categoria_id=str(row["category_id"]),
            nome=row["name"], gtin=row["gtin"], specs=row["specs"],
        )
