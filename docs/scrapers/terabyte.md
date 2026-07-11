# Terabyteshop Scraper

## Visão Geral

A integração com a **Terabyteshop** é composta por dois motores principais dentro da nossa arquitetura:
1. **Spider (`TerabyteSpider`)**: Responsável por navegar nas páginas de busca e descobrir novas URLs de produtos (SKUs).
2. **Scraper (`TerabyteScraper`)**: Responsável por entrar nas URLs descobertas e extrair os preços e disponibilidade.

## Abordagem Tecnológica: Scraping Baseado em HTML

Ao contrário do Mercado Livre, a Terabyteshop não fornece uma API REST pública e aberta. Portanto, a extração de dados é feita através da varredura do DOM (HTML) renderizado, imitando o comportamento de um navegador real.

### Evitando Bloqueios (Anti-Bot)

Para mitigar bloqueios rudimentares anti-bot da Terabyteshop, a arquitetura emprega o `Playwright` associado a técnicas de **interação humana simulada**:
- **`simulate_human_interaction(client)`**: Durante a etapa de `fetch()`, o scraper realiza pequenas pausas randômicas e "rola a página" (scroll) para simular o comportamento de leitura de um usuário humano.
- Isso assegura que a página carregue completamente recursos dinâmicos (como preços renderizados via JS de terceiros) e evite flags de tráfego robótico antes da leitura do HTML.

## Arquitetura de Parse

A extração de dados confia na injeção de dependência de seletores CSS armazenados no arquivo `data/selectors/terabyte.toml`.
Isso garante que, se o site mudar seu layout, não seja necessário refatorar o código Python; basta atualizar o arquivo `.toml`.

### 1. Descoberta (Spider)
O `TerabyteSpider` consulta a rota de busca global: `https://www.terabyteshop.com.br/busca?str=<keyword>`.
Ele processa a estrutura do grid (buscando as tags `a` da classe `tss-result-card`), captura as URLs brutas, normaliza-as, e então gera listas de `ProductSKU` estruturadas para o banco de dados.

### 2. Extração (Scraper)
O `TerabyteScraper` recebe o HTML bruto gerado pela etapa de rede e usa o `BeautifulSoup` (LXML) para a transformação em memória.
As principais tratativas envolvem:
- **Tratamento Monetário**: As strings brutas contendo `R$` e pontos milhares são purgadas através de RegEx (ex: `R$ 4.799,00` se converte no tipo forte `Decimal(4799.00)`).
- **Tratamento de Estoque**: A disponibilidade do produto é verificada tentando encontrar expressões de "esgotado" (ex: `Produto Esgotado`, `Avise-me`). Se detectada, ele persiste o produto como indisponível sem travar a execução por preços faltantes.
- **Limites de Falha**: O `parse()` falha deterministicamente e lança uma `SelectorOutdatedException` caso a Terabyteshop mude a classe principal do container de preços, abortando o processamento de forma segura.

## Estrutura do TOML (Seletores)

Os mapeamentos atuais ficam em `data/selectors/terabyte.toml`:
```toml
# Exemplo de configuração esperada
[v1]
title = "h1.tit-prod"
price_cash = "p#valVista"
price_installments = "p#valParcel"
installment_count = "span.text-parcelas"
out_of_stock = "Indisponível|Esgotado|Avise-me"
```

## Resolução de Problemas

Se o dashboard do Streamlit começar a ficar vazio de dados da Terabyteshop repentinamente:
1. **Verifique os Seletores**: Inspecione o HTML do site. A loja pode ter mudado a classe `#valVista` para outra tag. Atualize o `.toml`.
2. **Verifique Timeout**: O carregamento da página pode falhar se a Terabyteshop aplicar Cloudflare mais forte. Nesse caso, a exceção de timeout de `45000ms` do Playwright será disparada e anotada no log do Orquestrador (`data/orchestrator.log`).

## Referências
- Documentação principal de extração HTML via Playwright: `AGENTS.md`.
