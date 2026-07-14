# Terabyteshop Scraper

## Visão Geral

O `TerabyteScraper` (`src/scrapers/terabyte.py`) é responsável por extrair preço, parcelamento e disponibilidade de produtos da Terabyteshop. Ao contrário do Mercado Livre, a Terabyteshop não expõe uma API REST pública, então a extração é feita via scraping de HTML renderizado com Playwright.

A classe herda de `BaseScraper` e se registra automaticamente no orquestrador através do decorator `@register_scraper` (`src/core/registry.py`) — o único arquivo do scraper que precisa existir para que ele seja descoberto é o próprio módulo em `src/scrapers/`, importado automaticamente por `src/scrapers/__init__.py`. Não há necessidade de editar `main.py` para registrar a loja.

## Descoberta de SKUs

A antiga camada de "spider" (`TerabyteSpider`, que faria a varredura de páginas de busca) foi **descontinuada**: ela nunca chegou a ser efetivamente acionada pelo `DiscoveryEngine` e sua metade de rede (`fetch_search_page`) nunca foi implementada. Hoje a descoberta de SKUs é feita via manifesto estático (`data/target_urls.json`), carregado pelo `DiscoveryEngine` (`src/engine/discovery.py`) diretamente para a tabela `target_urls`. Ver `.agents/AGENTS.md` §5 para o racional dessa decisão.

## Transporte: Playwright (Browser)

`TerabyteScraper` usa `transport_type = "browser"` (o padrão herdado de `BaseScraper`), então o `PriceEngine` injeta uma `Page` do Playwright (via `BrowserFactory`), não um cliente HTTP puro. Isso é necessário porque o preço e a disponibilidade dependem de conteúdo renderizado via JavaScript no navegador.

### Fingerprint do navegador

O `BrowserFactory` (`src/core/browser.py`) não sobrescreve o `user_agent` do contexto — o Chromium instalado reporta sua própria identidade (versão, plataforma, `Sec-CH-UA`) de forma autêntica. Isso corrige um problema real encontrado durante investigação: por um tempo o `user_agent` estava fixado manualmente em `Chrome/122`, enquanto o binário real instalado já estava na v149 — uma inconsistência clássica de fingerprint que sistemas anti-bot usam como sinal. O viewport também é levemente randomizado (`1880–1920 x 1000–1080`) a cada contexto, e o `playwright-stealth` é aplicado em toda página criada.

### Simulação de comportamento humano

Durante o `fetch()`, o scraper chama `simulate_human_interaction()` (`src/core/utils.py`) antes de capturar o HTML:
- Pausa inicial randômica (0.8–2.2s), simulando o tempo de leitura antes de qualquer interação.
- Movimento de mouse por múltiplos waypoints com quantidade de passos variável (`_move_mouse_naturally`), em vez de saltos instantâneos entre pontos.
- Rolagem em incrementos desiguais, com chance de pequeno scroll de volta (`_scroll_naturally`).
- Hover ocasional (60% de chance) sobre um link ou imagem real da página (`_hover_random_element`), gerando eventos de `mouseover` que um visitante passivo produziria.
- Detecção e interação com iframes de Cloudflare, se presentes.

## ⚠️ Achado importante: "indisponível" nem sempre é bloqueio anti-bot

Durante uma investigação de suposto bloqueio anti-bot (sessão de hardening desta documentação), uma varredura diagnóstica ao vivo mostrou que a Terabyteshop **não estava bloqueando o scraper**: a resposta era um HTTP 200 legítimo, com o título e os seletores de preço/título presentes normalmente. Ao cruzar os resultados de um lote completo de SKUs, o padrão foi claro:
- Toda SKU de **RTX 5070** (não-Ti) retornava preço real, `Available: True`.
- Toda SKU de **RTX 5070 Ti** "falhando" mostrava uma página genuína de **"PRODUTO INDISPONÍVEL"** com formulário real de "Avise-me" — não uma tela de CAPTCHA ou desafio.

Ou seja: `is_available = False` + `price_cash = 0.00` frequentemente significa **estoque real esgotado**, não um bloqueio. Scripts de reCAPTCHA/Cloudflare presentes no HTML (usados para checkout/prevenção de fraude, por exemplo) não implicam necessariamente que a página atual foi bloqueada — confirme sempre olhando o HTML/screenshot real antes de assumir anti-bot.

Se antes de investigar você suspeitar de bloqueio genuíno, sinais reais a procurar no documento capturado: título da página contendo `"Just a moment"`, presença de `challenge-platform` ativo bloqueando o conteúdo principal, ou ausência total dos seletores de título/preço (o que dispara `SelectorOutdatedException`, ver abaixo).

## Extração (`parse()`)

O `parse()` é uma função pura (sem I/O), determinística, e usa `BeautifulSoup` + `lxml` sobre o HTML já capturado. Os seletores vêm de `data/selectors/terabyte.toml`:

```toml
[v1]
title = ".tit-prod"
price_cash = "#valVista"
price_installments = "#valParc"
installment_count = "#nParc"
out_of_stock = "indisponível|Avise-me"
```

Lógica de parse:
1. **Título**: se o seletor `.tit-prod` não for encontrado, levanta `SelectorOutdatedException` — sinal forte de que o layout do site mudou (não confundir com estoque zerado, que é tratado separadamente).
2. **Preço à vista**: extraído e convertido via `clean_brl_price()` (`src/core/parsing_utils.py`, compartilhado com os outros scrapers) — remove `R$`, pontos de milhar, troca vírgula por ponto.
3. **Disponibilidade**: `has_out_of_stock_marker()` procura o padrão `indisponível|Avise-me` no texto da página. Se o produto estiver indisponível e nenhum preço for encontrado, o preço é gravado como `Decimal("0.00")` em vez de descartar o registro — assim o histórico mostra explicitamente "sem estoque" no dashboard, em vez de um buraco silencioso.
4. **Parcelamento**: preço parcelado (`#valParc`) e quantidade de parcelas (`#nParc`), quando presentes.
5. **Desconto**: calculado via `compute_discount()` (parcelado − à vista), mesmo helper usado por Kabum e Mercado Livre.
6. O `PriceContract` final é montado por `build_price_contract()` (`src/core/contract_factory.py`), que preenche automaticamente `store_name`, `search_keyword`, `product_url`, `brand`/`model` a partir do `scraper`/`sku` — o `parse()` só precisa fornecer os campos que variam.

## Observabilidade

Toda execução (agendada via cron ou manual) fica registrada na tabela `scraper_runs` e visível na tela **📡 Execuções dos Scrapers** do dashboard Streamlit (`src/ui/pages/1_Execucoes.py`):
- Status ao vivo (Rodando / Concluído / Falhou), com auto-refresh a cada 3s.
- Histórico recente por loja, incluindo mensagem de erro quando aplicável.
- Botão **"Rodar Agora"** por loja, que enfileira um pedido processado pelo orquestrador em até 5s (`TriggerProcessor`, `src/engine/trigger_processor.py`) — útil para forçar uma nova tentativa da Terabyteshop sem esperar o próximo horário do cron.

Logs detalhados (incluindo tracing de protocolo do Playwright) ficam em `data/orchestrator.log` e em `docker logs pricing_orchestrator` quando rodando via Docker.

## Resolução de Problemas

1. **`SelectorOutdatedException` para `title` ou `price_cash`**: o layout da página mudou de fato. Inspecione o HTML atual e atualize `data/selectors/terabyte.toml` — não é necessário alterar `terabyte.py`.
2. **Preço zerado / `Available: False` para um produto que você sabe estar em estoque**: confirme primeiro se não é estoque real esgotado (veja a seção de achado acima) antes de assumir bug ou bloqueio. Rode uma verificação manual pela tela de Execuções ou visite a URL diretamente.
3. **Timeout no `fetch()` (45000ms)**: pode indicar Cloudflare mais agressivo naquele momento ou lentidão real do site. A exceção fica registrada no log do orquestrador com o motivo.
4. **Quer rodar só a Terabyteshop manualmente**: use o botão "Rodar Agora" na tela de Execuções, ou `python scripts/run_all_scrapers.py` localmente (roda todas as lojas registradas de uma vez).

## Referências
- Arquitetura e convenções gerais: `.agents/AGENTS.md`
- Contrato de dados compartilhado: `src/core/contract.py`
- Helpers de parsing compartilhados: `src/core/parsing_utils.py`, `src/core/contract_factory.py`
