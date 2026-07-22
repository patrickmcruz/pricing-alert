# Arquitetura do Sistema & Visão Geral 🏗️

O **GPU Price Tracker** é um sistema modular, resiliente e orientado a testes construído para automação da extração de preços, estruturação de catálogo e alertas de e-commerce.

---

## 1. Visão Geral da Arquitetura

O sistema é dividido em três camadas principais:

```mermaid
graph TD
    A["Agendador & Orquestrador (APScheduler / main.py)"] --> B["Discovery Engine"]
    A --> C["PriceEngine (Scraper Pipeline)"]
    
    B --> D["TitleParserRegistry (Parser de Títulos)"]
    D --> E["PostgreSQL Database (pricing)"]
    
    C --> F["Scraper Engines (Pichau, KaBuM, Terabyte, ML, Amazon)"]
    F --> G["PriceContract (Pydantic V2)"]
    G --> E
    
    E --> H["AlertDispatcher (Alertas & Notificações)"]
    E --> I["Streamlit Dashboard (Dashboard.py & Views SQL)"]
```

---

## 2. Ciclo de Vida da Execução (Sequence Diagram)

O diagrama abaixo ilustra o fluxo completo desde a inicialização do orquestrador até a atualização do banco e disparo de alertas:

```mermaid
sequenceDiagram
    autonumber
    participant Main as Orchestrator (main.py)
    participant Discovery as DiscoveryEngine
    participant Engine as PriceEngine
    participant Scraper as Concrete Scraper (ex: Pichau)
    participant DB as PostgreSQL
    participant Dispatcher as AlertDispatcher

    Main->>DB: initialize_schema()
    Main->>Discovery: run_discovery()
    Discovery->>DB: Carrega target_urls
    Discovery->>DB: Upsert Produtos, Marcas & Specs
    Main->>Engine: build_schedule() & start()
    
    loop Execução Agendada (Cron)
        Engine->>Scraper: execute(sku, client)
        Scraper->>Scraper: fetch() -> HTML / JSON
        Scraper->>Scraper: parse() -> PriceContract
        Scraper-->>Engine: PriceContract
        Engine->>DB: Persiste PriceObservation
        Engine->>Dispatcher: handle_price(price_contract)
        Dispatcher->>DB: Avalia AlertRules & Dispara Alerta
    end
```

---

## 3. Padrões de Projeto Aplicados

1. **Inversão de Controle & Injeção de Dependências (IoC):** O agendador `PriceEngine` e os scrapers nunca instanciam diretamente clientes HTTP ou contextos de navegador Playwright; eles recebem `ClientFactory` via injeção.
2. **Repository Pattern:** O acesso aos dados é encapsulado atrás de repositórios assíncronos (`PostgresPriceRepository`, `PostgresCatalogRepository`, `PostgresAlertRepository`).
3. **Registry Self-Registration (`@register_scraper`):** Cada scraper se auto-registra ao ser importado, eliminando a necessidade de modificar arquivos centrais para adicionar novas lojas.
