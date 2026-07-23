# Future App Improvements

Created at: 05/07/2026 00:56h

The current architecture is actually in a very healthy state—especially with the recent Test-Driven Development (TDD) improvements, Dependency Injection via Factories, and externalized TOML selectors. You’ve built a highly maintainable system!

However, if we put on a "Senior Staff Engineer" hat and look at production-readiness, there are a few significant improvements we should make. Here are my top recommendations for architectural and engineering upgrades:

### 1. 🛡️ Enable Browser Stealth (Critical for Scraping)
In `pyproject.toml`, you declare `playwright-stealth` as a dependency. However, in `src/core/browser.py`, its usage is just a comment (`# Add stealth script if needed`). E-commerce sites (like Kabum) use aggressive bot protection (Cloudflare/Akamai). 
**Improvement**: We must actively inject the stealth plugin into the `Page` object inside `BrowserFactory` to prevent the scrapers from being permanently IP-banned.

### 2. 🛜 Network Resilience & Retries
Currently, if `KabumScraper.fetch()` encounters a brief network hiccup or timeout, it swallows the error, logs it, and returns an empty string. The scheduler then fails to parse the page and skips the product until the next hour.
**Improvement**: Implement an automated retry mechanism (using a library like `tenacity` or a custom async loop) with exponential backoff. If a page fails to load, the scraper should try 2 or 3 more times before giving up.

### 3. 💾 Database Connection Pooling
In `SQLitePriceRepository`, every single method (`save_prices`, `save_skus`, `get_target_skus`) opens a brand new connection using `async with aiosqlite.connect(...)` and then closes it immediately. While SQLite is fast, doing this rapidly across dozens of parallel cron jobs creates unnecessary I/O overhead.
**Improvement**: The `PriceRepository` should maintain a single, long-lived connection (or a connection pool) that is opened when the Engine starts and cleanly closed when the application shuts down.

### 4. 🗃️ Robust Schema Migrations
In `sqlite_repository.py`, we handle database migrations by blindly running `ALTER TABLE` and swallowing `aiosqlite.OperationalError` if the column already exists. This works for a prototype, but is dangerous in production.
**Improvement**: Implement a simple `schema_version` table. Before running any `ALTER` commands, the repository checks the current database version and sequentially applies only the missing SQL scripts.

### 5. 📝 Log Rotation
Right now, `src/core/config.py` pipes all logs directly to standard output (`logging.basicConfig`). For a background service running 24/7, this means logs are either lost if the terminal closes, or they will grow indefinitely if piped to a basic file.
**Improvement**: Configure Python’s `RotatingFileHandler` or `TimedRotatingFileHandler` so that logs are safely written to a `logs/` directory, keeping only the last 7 or 14 days of logs to prevent disk exhaustion.

### 6. 🧬 Recomendações de Evolução Arquitetural (Próximos Passos Enterprise)
Se o aplicativo fosse evoluir para um cenário de alta escala ou múltiplos usuários, as seguintes evoluções arquiteturais trariam valor agregado:

#### Transactional Outbox Pattern (Event Bus Assíncrono)

- Cenário: Atualmente o `AlertDispatcher`
 envia notificações diretamente após a persistência.
- Evolução: Caso o Telegram passe por instabilidade ou novos canais de notificação sejam adicionados, salvar o evento de alerta em uma tabela de outbox no Postgres e processá-lo via worker dedicado garante resiliência e retentativas (retry with exponential backoff) sem bloquear o ciclo do scraper.

#### Circuit Breaker por Loja

- Cenário: Se um e-commerce implementar bloqueio agressivo por Cloudflare/bot mitigation temporário.
- Evolução: Implementar o padrão Circuit Breaker no `PriceEngine`. Caso N requisições consecutivas retornem erro 403 ou timeout, o estado da loja muda para OPEN (pausado) por um período de cooldown (ex: 30 minutos) antes de tentar uma requisição HALF-OPEN.

#### Particionamento de Dados no PostgreSQL

- Cenário: A tabela price_observations acumula registros continuamente em execuções de cron.
- Evolução: Conforme o volume de observações de histórico cresça para centenas de milhares de linhas, aplicar Range Partitioning por mês/ano no schema (`schema.py`) otimizará as consultas analíticas de variação de preços no dashboard Streamlit.

#### Telemetria e Observabilidade (OpenTelemetry)

- Cenário: Monitorar a saúde dos scrapers de forma quantitativa.
- Evolução: Adicionar exportação de métricas (taxa de falha por seletor, tempo de execução por SKU, latência de resposta por e-commerce) para Prometheus/Grafana.
