from abc import ABC, abstractmethod
from typing import Any, List, Optional

from src.core.catalog import Categoria, Marca, Produto, ResolvedProduto


class CatalogRepository(ABC):
    """
    Abstract interface for the normalized product catalog: Categoria (product
    category), Marca (brand/board partner), and Produto (a specific
    marca+categoria+variant combination, with category-specific attributes in
    Produto.specs). anuncio/coleta_preco reference Produto by id instead of
    storing free-text brand/model.
    """

    @abstractmethod
    async def get_or_create_categoria(
        self, nome: str, slug: str, parent_id: Optional[str] = None
    ) -> Categoria:
        """Case-insensitive get-or-create by slug."""

    @abstractmethod
    async def get_or_create_marca(self, nome: str) -> Marca:
        """Case-insensitive get-or-create by name."""

    @abstractmethod
    async def get_or_create_produto(
        self,
        marca_id: str,
        categoria_id: str,
        nome: str,
        specs: Optional[dict[str, Any]] = None,
    ) -> Produto:
        """Case-insensitive get-or-create by (marca_id, categoria_id, nome, specs['chipset'])."""

    @abstractmethod
    async def get_produto(self, produto_id: str) -> Optional[Produto]:
        """Returns a Produto by id, or None if it doesn't exist."""

    @abstractmethod
    async def list_marcas(self) -> List[Marca]: ...

    @abstractmethod
    async def list_categorias(self) -> List[Categoria]: ...

    @abstractmethod
    async def list_produtos_resolved(self, categoria_slug: Optional[str] = None) -> List[ResolvedProduto]:
        """Every Produto joined with its Marca/Categoria names, for display.
        Filtered to a single category when categoria_slug is given."""
