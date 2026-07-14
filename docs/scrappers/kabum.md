# Kabum Scraper

## Visão Geral

O `KabumScraper` (`src/scrapers/kabum.py`) extrai preço, parcelamento e disponibilidade de produtos da Kabum. Assim como a Terabyteshop, a Kabum não expõe uma API pública, então a extração é feita via scraping de HTML renderizado com Playwright.

A classe herda de `BaseScraper` e se registra automaticamente no orquestrador via `@register_scraper` (`src/core/registry.py`) — o único arquivo necessário para adicionar/manter esta loja é o próprio módulo em `src/scrapers/`, importado automaticamente por `src/scrapers/__init__.py`.

## Descoberta de SKUs

Assim como as demais lojas baseadas em HTML, a Kabum não usa mais a antiga camada de "spider" (descontinuada — ver `docs/scrapers/terabyte.md` para o histórico). SKUs vêm do manifesto estático `data/target_urls.json`, carregado pelo `DiscoveryEngine` (`src/engine/discovery.py`) diretamente para a tabela `target_urls`.

## Transporte: Playwright (Browser)

`KabumScraper` usa `transport_type = "browser"` (padrão herdado de `BaseScraper`), então o `PriceEngine` injeta uma `Page` do Playwright via `BrowserFactory`. O `fetch()` navega com `wait_until="networkidle"` e timeout de `30000ms`:

```python
await client.goto(str(sku.product_url), wait_until="networkidle", timeout=30000)
return await client.content()
```

### ⚠️ Diferença notável em relação à Terabyteshop

Ao contrário do `TerabyteScraper`, o `fetch()` da Kabum **não chama** `simulate_human_interaction()` (`src/core/utils.py`) — não há movimento de mouse, scroll ou pausa de leitura simulados antes de capturar o HTML. As duas lojas compartilham o mesmo `BrowserFactory` (fingerprint autêntico do Chromium, viewport randomizado, `playwright-stealth` aplicado), então a Kabum ainda se beneficia do hardening de fingerprint, mas não do hardening comportamental. Isso não é um bug corrigido nesta sessão — é uma inconsistência real e conhecida entre os dois scrapers, documentada aqui para quem for investigar um eventual bloqueio futuro: se a Kabum começar a apresentar bloqueios que a Terabyteshop não apresenta, considerar adicionar a mesma simulação de interação humana aqui primeiro, antes de assumir um problema mais profundo.

## Extração (`parse()`)

Função pura, sem I/O, usando `BeautifulSoup` + `lxml`. Os seletores vêm de `data/selectors/kabum.toml`, que define duas versões:

```toml
[v1]
title = "h1"
price_cash = ".finalPrice"
price_installments = ".regularPrice"
out_of_stock = "indisponível"

[v2]
title = "h1"
price_cash = "h4.text-4xl"
price_installments = "span.block.my-12 b.text-xs.font-bold"
installment_count = "span.block.my-12"
out_of_stock = "indisponível"
```

**Importante**: apesar de existirem duas versões no `.toml` (sugerindo suporte a fallback entre layouts), o código atual usa **sempre `v2`**, fixado diretamente em `parse()` (`parser_version = "v2"`). Não há tentativa automática de `v1` como fallback caso `v2` falhe — se a Kabum reverter para o layout antigo, será necessário trocar a versão manualmente no código ou implementar a cadeia de fallback (ver `.gemini/.promtps/Refactoration/scraper-versioning/analyze.md` para a ideia original de "Strategy Pattern versionado", nunca implementada).

Lógica de parse:
1. **Título e preço à vista**: se `h1` ou `h4.text-4xl` não forem encontrados, levanta `SelectorOutdatedException`.
2. **Preço inválido → registro descartado**: diferente da Terabyteshop (que grava `Decimal("0.00")` para itens indisponíveis), a Kabum **descarta o registro inteiro** (`return None`) se `price_cash` for `None` ou `<= 0` — mesmo que o produto esteja de fato apenas fora de estoque. Não fica um "indisponível" explícito no histórico para a Kabum como fica para a Terabyteshop; o item simplesmente não gera uma linha naquele ciclo.
3. **Correção de parcelamento**: heurística específica desta loja —
   ```python
   if price_installments and price_cash and installment_count:
       if price_installments < price_cash:
           price_installments = price_installments * installment_count
   ```
   O seletor `installment_count` às vezes captura o valor **de uma única parcela** em vez do total parcelado. Se o valor extraído for menor que o preço à vista (sinal de que é per-parcela, não o total), o código multiplica pelo número de parcelas para normalizar ao total — mesma convenção usada pelas outras lojas (`price_installments` = valor total parcelado, não o valor da parcela individual).
4. **Disponibilidade**: `has_out_of_stock_marker()` (`src/core/parsing_utils.py`, compartilhado com Terabyteshop) procura o padrão `indisponível` no texto da página.
5. **Desconto**: `compute_discount()` (parcelado − à vista), mesmo helper compartilhado por todos os scrapers.
6. O `PriceContract` final é montado por `build_price_contract()` (`src/core/contract_factory.py`), preenchendo automaticamente `store_name`, `search_keyword`, `product_url`, `brand`/`model` a partir do `scraper`/`sku`.

## Observabilidade

Toda execução (agendada via cron ou manual) fica registrada na tabela `scraper_runs` e visível na tela **📡 Execuções dos Scrapers** do dashboard Streamlit (`src/ui/pages/1_Execucoes.py`):
- Status ao vivo (Rodando / Concluído / Falhou), com auto-refresh a cada 3s.
- Histórico recente por loja, incluindo mensagem de erro quando aplicável.
- Botão **"Rodar Agora"** por loja, que enfileira um pedido processado pelo orquestrador em até 5s (`TriggerProcessor`, `src/engine/trigger_processor.py`).

Logs detalhados ficam em `data/orchestrator.log` e em `docker logs pricing_orchestrator` quando rodando via Docker.

## Resolução de Problemas

1. **`SelectorOutdatedException` para `title` ou `price_cash`**: o layout mudou. Inspecione o HTML atual e atualize `data/selectors/kabum.toml` (bloco `[v2]`, que é o único efetivamente usado hoje) — não é necessário alterar `kabum.py`.
2. **Produto some do histórico sem erro nenhum**: lembre que, ao contrário da Terabyteshop, um produto fora de estoque na Kabum não gera um registro "indisponível" — ele é silenciosamente descartado (`parse()` retorna `None`). Confira `data/orchestrator.log` por `"No price extracted for..."` para confirmar que foi esse o caso, em vez de assumir falha de seletor.
3. **Parcelamento aparentando valor errado (muito menor que o preço à vista)**: revise a heurística de correção descrita acima — se a Kabum mudar o layout de forma que o texto do seletor `installment_count` deixe de conter algo no formato `"10x"`, a extração de `installment_count` falha silenciosamente (é envolvida em `try/except` com log de `warning`) e a correção não é aplicada.
4. **Quer rodar só a Kabum manualmente**: use o botão "Rodar Agora" na tela de Execuções, ou `python scripts/run_all_scrapers.py` localmente (roda todas as lojas registradas de uma vez).

## Referências
- Arquitetura e convenções gerais: `.agents/AGENTS.md`
- Contrato de dados compartilhado: `src/core/contract.py`
- Helpers de parsing compartilhados: `src/core/parsing_utils.py`, `src/core/contract_factory.py`
- Comparação com a outra loja baseada em HTML: `docs/scrapers/terabyte.md`
