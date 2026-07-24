# Mercado Livre Scraper & Spider Integration 🛒

Documentação técnica da integração com a **API Pública Oficial do Mercado Livre** para descoberta e raspagem de ofertas de GPUs.

---

## 🏗️ Arquitetura da Integração

A integração com o Mercado Livre divide-se em dois módulos fundamentais:

```mermaid
flowchart TD
    subgraph Configuração
        A[config.toml / settings.default_gpus]
    end

    subgraph 1. Descoberta de SKUs (MercadoLivreSpider)
        A -->|Keywords Ex: rtx 5070| B[src/spiders/mercadolivre.py]
        B -->|OAuth Client Credentials| C[POST /oauth/token]
        C -->|Access Token| D[GET /products/search?status=active&site_id=MLB]
        D -->|Filtro Estrito de Títulos| E[Salva em target_urls & listings]
    end

    subgraph 2. Extração de Preços (MercadoLivreScraper)
        E --> F[src/scrapers/mercadolivre.py]
        F -->|GET /products/MLBxxxx| G[PriceContract Pydantic V2]
        G --> H[PostgreSQL price_observations]
    end
```

---

## 🔐 1. Autenticação OAuth 2.0

Para contornar o firewall antibot (Cloudflare/Datadome) do Mercado Livre em buscas web, o sistema consome diretamente os endpoints REST oficiais da API do Mercado Livre.

### Configuração de Credenciais no `.env`:
```env
MERCADOLIVRE_APP_ID="seu_app_id"
MERCADOLIVRE_APP_SECRET_KEY="sua_secret_key"
```

Se as credenciais estiverem preenchidas, a aplicação realiza autenticação automática via o endpoint `https://api.mercadolibre.com/oauth/token` (grant type `client_credentials`) e injeta o cabeçalho `Authorization: Bearer <token>`.

---

## 🕷️ 2. Mercado Livre Spider (`MercadoLivreSpider`)

O spider de descoberta de ofertas ([`src/spiders/mercadolivre.py`](../../src/spiders/mercadolivre.py)) é responsável por consultar os catálogos do Mercado Livre e registrar automaticamente novos SKUs no banco de dados.

### Características Principais:
* **Transporte Puro HTTP (`transport_type = "http"`):** Sem custo computacional de renderização de Chromium/Playwright.
* **Leitura Dinâmica:** Consome dinamicamente os modelos definidos em `config.toml` (`settings.default_gpus`).
* **Filtragem Inteligente de Títulos:** Filtra e ignora automaticamente anúncios que não sejam GPUs avulsas (`_EXCLUDED_TITLE_WORDS`), como:
  * Notebooks e Laptops Gamer.
  * PCs Montados / Desktops Completos.
  * Cabos Risers, Suportes, Waterblocks, Adesivos e Extensores.

### Como Executar a Descoberta de SKUs:
```bash
python scripts/run_gpu_spider_discovery.py
```

---

## 🛒 3. Mercado Livre Scraper (`MercadoLivreScraper`)

O scraper de extração ([`src/scrapers/mercadolivre.py`](../../src/scrapers/mercadolivre.py)) visita periodicamente os SKUs descobertos e extrai os preços à vista, parcelado e status de estoque.

* **Normalização:** Todos os dados extraídos são validados contra o modelo `PriceContract` (Pydantic V2) e salvos na tabela `price_observations` do PostgreSQL.

---

## 🧪 4. Suíte de Testes Automatizados

A integração conta com cobertura unitária completa em [`tests/unit/test_mercadolivre_spider.py`](../../tests/unit/test_mercadolivre_spider.py):

```bash
pytest tests/unit/test_mercadolivre_spider.py
```
