# Implementação do Mercado Livre Scraper

A tarefa de inclusão do scraper do Mercado Livre foi concluída seguindo estritamente a arquitetura estipulada para o projeto (Pytest, Injeção de Dependências, Externalização de TOML).

## Mudanças Realizadas

1. **Inserção do Link da RTX 5070 no DB**:
   - Criamos e executamos um script (`setup_ml.py`) que garantiu que a URL alvo e suas características (`PNY`, `rtx 5070`) fossem inseridas nativamente no SQLite `prices.db` (tabela `target_urls`). A orquestração agora irá capturar esta placa da PNY nas próximas runs.

2. **Criação dos Seletores TOML**:
   - O arquivo `data/selectors/mercado-livre.toml` foi criado contendo os nós CSS padrão do ML que indicam preço e parcelamento. Utilizou-se o versionamento interno `[v1]`.

3. **Lógica de Parser e BaseScraper**:
   - `src/scrapers/mercadolivre.py`: A classe `MercadoLivreScraper` foi criada herdando de `BaseScraper`.
   - Adicionada lógica robusta de Regex que varre os nós de texto das parcelas e valores para determinar dinamicamente o número de prestações e prever falhas de HTML causadas por espaços inconsistentes injetados pelo React do Mercado Livre.
   - Pydantic validou os modelos e as regras `frozen=True` com `currency` explícita foram atendidas.

4. **Registro no Motor Principal**:
   - `main.py` foi atualizado para carregar a instância `MercadoLivreScraper()` no loop do escalonador.

## QA e Verificação

> [!TIP]
> **Testes Automatizados:** Foram criados testes unitários completos em `tests/unit/test_mercadolivre_parser.py` validando todos os edge-cases (preço à vista vs parcelado). Executamos localmente o contêiner `pricing_orchestrator` e rodamos o **pytest**, atingindo **100% de sucesso**.

- **Anti-Bot Alert:** Durante os testes de rede ao vivo, identificamos que o ML usa uma detecção rígida via Cloudflare/Meli (o famoso "Tráfego Suspeito"). O método `fetch()` do Playwright contornará parte disso usando o Context Stealth. No futuro, considere usar a biblioteca `playwright-stealth` ativamente ou rotacionar Proxies Residenciais.
- A orquestração via Docker foi reconstruída com sucesso e o ambiente roda saudável no `docker-compose`.
