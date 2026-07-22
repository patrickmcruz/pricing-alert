# Guia: Como Adicionar Novas Categorias de Hardware 🛠️

Este guia passo a passo explica como adicionar o rastreamento e parsing de novas categorias de hardware (ex: **Placa Mãe**, **Memória RAM**, **Processadores/CPU**, **SSDs**) sem precisar alterar a estrutura de tabelas do PostgreSQL.

---

## Passo 1: Criar o Modelo Pydantic em `src/core/specs.py`

Defina uma nova classe representando as especificações da categoria:

```python
class CPUSpecs(BaseModel):
    """Especificações para Processadores (CPU)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    socket: str = Field(..., description="Soquete da CPU (ex: AM5, LGA1700)")
    cores: int = Field(..., description="Número de núcleos físicos")
    threads: int = Field(..., description="Número de threads")
    base_clock_ghz: float = Field(..., description="Frequência base em GHz")
    boost_clock_ghz: Optional[float] = Field(default=None, description="Frequência boost em GHz")
    has_integrated_gpu: bool = Field(default=False, description="Possui vídeo integrado")
    mpn: Optional[str] = Field(default=None, description="Código da peça do fabricante")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
```

---

## Passo 2: Adicionar o Parser em `src/core/title_parser.py`

Adicione o método estático de parsing de título no `TitleParserRegistry`:

```python
@staticmethod
def parse_cpu(raw_title: str) -> CPUSpecs:
    title_upper = raw_title.upper()

    # Exemplo simples de parsing de núcleos e soquete
    socket = "AM5" if "AM5" in title_upper else "LGA1700"
    cores_match = re.search(r"(\d+)\s*NÚCLEOS|\b(\d+)C\b", title_upper)
    cores = int(cores_match.group(1) or cores_match.group(2)) if cores_match else 8

    return CPUSpecs(
        socket=socket,
        cores=cores,
        threads=cores * 2,
        base_clock_ghz=3.8,
    )
```

---

## Passo 3: Cadastrar a Categoria e URLs no Manifest

Adicione a nova categoria via `DiscoveryEngine` ou insira na tabela `target_urls`:

```python
categoria = await catalog_repo.get_or_create_categoria("Processador", "cpu")
```

---

## Passo 4: Atualizar o Dashboard Streamlit (`src/ui/Dashboard.py`)

No Streamlit, adicione o filtro por especificações da nova categoria lendo diretamente do campo `specs` da View `vw_dashboard_products` ou via filtro dinâmico de JSONB!
