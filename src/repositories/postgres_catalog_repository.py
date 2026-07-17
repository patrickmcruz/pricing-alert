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
            row = await db.fetchrow("SELECT id, nome, slug, parent_id FROM categoria WHERE slug = $1", slug)
            if row:
                return self._row_to_categoria(row)

            categoria = Categoria(id=str(uuid4()), nome=nome.strip(), slug=slug, parent_id=parent_id)
            await db.execute(
                "INSERT INTO categoria (id, nome, slug, parent_id, criado_em) VALUES ($1, $2, $3, $4, $5)",
                categoria.id, categoria.nome, categoria.slug, categoria.parent_id,
                datetime.now(timezone.utc),
            )
            logger.info("Created categoria %s (%s)", categoria.nome, categoria.id)
            return categoria

    async def get_or_create_marca(self, nome: str) -> Marca:
        nome = nome.strip()
        async with connect(self.dsn) as db:
            row = await db.fetchrow("SELECT id, nome FROM marca WHERE LOWER(nome) = LOWER($1)", nome)
            if row:
                return Marca(id=str(row["id"]), nome=row["nome"])

            marca = Marca(id=str(uuid4()), nome=nome)
            await db.execute(
                "INSERT INTO marca (id, nome, criado_em) VALUES ($1, $2, $3)",
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
                SELECT id, marca_id, categoria_id, nome, gtin, specs FROM produto
                WHERE marca_id = $1 AND categoria_id = $2 AND LOWER(nome) = LOWER($3)
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
                "INSERT INTO produto (id, marca_id, categoria_id, nome, gtin, specs, criado_em) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                produto.id, produto.marca_id, produto.categoria_id, produto.nome, produto.gtin,
                produto.specs, datetime.now(timezone.utc),
            )
            logger.info("Created produto %s (%s)", produto.nome, produto.id)
            return produto

    async def get_produto(self, produto_id: str) -> Optional[Produto]:
        async with connect(self.dsn) as db:
            row = await db.fetchrow(
                "SELECT id, marca_id, categoria_id, nome, gtin, specs FROM produto WHERE id = $1",
                produto_id,
            )
            return self._row_to_produto(row) if row else None

    async def list_marcas(self) -> List[Marca]:
        async with connect(self.dsn) as db:
            rows = await db.fetch("SELECT id, nome FROM marca ORDER BY nome")
            return [Marca(id=str(row["id"]), nome=row["nome"]) for row in rows]

    async def list_categorias(self) -> List[Categoria]:
        async with connect(self.dsn) as db:
            rows = await db.fetch("SELECT id, nome, slug, parent_id FROM categoria ORDER BY nome")
            return [self._row_to_categoria(row) for row in rows]

    async def list_produtos_resolved(self, categoria_slug: Optional[str] = None) -> List[ResolvedProduto]:
        query = """
            SELECT p.id, ma.nome AS marca_nome, c.nome AS categoria_nome, p.nome, p.specs
            FROM produto p
            JOIN marca ma ON ma.id = p.marca_id
            JOIN categoria c ON c.id = p.categoria_id
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
                    nome=row["nome"],
                    specs=row["specs"],
                )
                for row in rows
            ]

    @staticmethod
    def _row_to_categoria(row) -> Categoria:
        return Categoria(
            id=str(row["id"]), nome=row["nome"], slug=row["slug"],
            parent_id=str(row["parent_id"]) if row["parent_id"] else None,
        )

    @staticmethod
    def _row_to_produto(row) -> Produto:
        return Produto(
            id=str(row["id"]), marca_id=str(row["marca_id"]), categoria_id=str(row["categoria_id"]),
            nome=row["nome"], gtin=row["gtin"], specs=row["specs"],
        )
