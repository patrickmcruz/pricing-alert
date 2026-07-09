# [Goal Description]

Incluir o novo scraper para o Mercado Livre e adicionar o link da Placa de Vídeo PNY RTX 5070 OC na lista de monitoramento. Seguindo a arquitetura orientada a testes, o scraper será injetado no motor de orquestração existente, utilizando Playwright e seletores externalizados em TOML.

## User Review Required

> [!IMPORTANT]
> - O nome da loja adotado será **`mercado-livre`** (conforme já existente no `target-stores-list.json`).
> - A inserção da URL será feita diretamente na tabela `target_urls` via script de setup.
> - O Mercado Livre possui forte proteção antibot. O uso do `playwright-stealth` já mapeado anteriormente na arquitetura ajudará, mas a execução contínua via servidor pode exigir adaptações (como uso de proxies) no futuro.

## Proposed Changes

### Database & Discovery (Setup)
A URL informada não vem da busca automática (spiders), mas de uma adição manual. Criaremos um script para popular o banco de dados inicial ou executaremos o insert diretamente:

#### [NEW] `scripts/add_ml_url.py`
Script pontual para inserir a URL no SQLite `target_urls` com `store_name='mercado-livre'`, `brand='PNY'`, e `model='rtx 5070'`.

---

### Core Data & Selectors

#### [NEW] `data/selectors/mercado-livre.toml`
Arquivo TOML contendo os seletores CSS para extrair:
- Preço à vista (`price_cash`)
- Preço parcelado (`price_installments`) e quantidade de parcelas

---

### Scraper Implementation

#### [NEW] `src/scrapers/mercadolivre.py`
Implementação da classe `MercadoLivreScraper(BaseScraper)`.
- **`fetch()`**: Utilizará a factory do cliente (Playwright) injetada.
- **`parse()`**: Usará BeautifulSoup e os seletores do arquivo TOML para extrair os preços, garantindo que retorne um `PriceContract` padronizado. Lançará `SelectorOutdatedException` se não encontrar os nós principais no DOM.

---

### Orchestrator Registration

#### [MODIFY] `main.py`
- Importar `MercadoLivreScraper`.
- Adicioná-lo à lista de instâncias enviadas para `engine.register_scrapers()`.

---

### QA & Tests

#### [NEW] `tests/fixtures/mercadolivre.html`
Fixture estática com o HTML real do produto, garantindo que os testes não façam I/O de rede.

#### [NEW] `tests/unit/test_mercadolivre_parser.py`
Testes unitários rigorosos (Pytest) validando o método `parse()` isoladamente.

## Verification Plan

### Automated Tests
- `pytest tests/unit/test_mercadolivre_parser.py`
- `pytest tests/` (garantir cobertura da suite completa)
- Validação estática: `mypy`, `black`, `ruff`.

### Manual Verification
- Executar `python main.py` e observar nos logs se o orquestrador carrega com sucesso o `MercadoLivreScraper`.
- Confirmar no banco de dados SQLite (`prices.db`) se o scraping retornou os valores `price_cash` e `price_installments` corretamente da URL da PNY.
