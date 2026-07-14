# Mercado Livre Scraper

## Visão Geral

O scraper do Mercado Livre (`MercadoLivreScraper`) é responsável por extrair preços e informações de disponibilidade de produtos (como placas de vídeo) dentro do ecossistema do Mercado Livre.

## O Desafio: WAF e CAPTCHAs

Inicialmente, a arquitetura do projeto utilizava o `Playwright` para realizar o web scraping do HTML das páginas de produtos, imitando o comportamento de um navegador real.
No entanto, o Mercado Livre emprega um sistema agressivo de **Web Application Firewall (WAF)** e **Cloudflare CAPTCHAs** (como o desafio `verifyChallenge`).

Isso tornava o web scraping convencional extremamente instável:
1. O HTML da página de produto muitas vezes não era retornado pelo servidor, mas sim uma página de bloqueio ou desafio humano.
2. Como resultado, os seletores CSS configurados externamente (armazenados em `data/selectors/mercado-livre.toml`) falhavam constantemente, gerando erros crônicos de `SelectorOutdatedException`.
3. O orquestrador falhava em coletar os dados, criando lacunas ("gaps") na visualização e inviabilizando análises históricas no dashboard do Streamlit.

## A Solução: API Oficial de Desenvolvedores

Para garantir estabilidade de 100%, determinismo e alta resiliência, a extração via Playwright tradicional (renderização de interface) foi descontinuada e substituída pela **API REST Oficial do Mercado Livre**.

Ao fazer as extrações se identificando formalmente como uma aplicação desenvolvedora através da API, o sistema não é submetido aos bloqueios do WAF.

### Funcionamento da Arquitetura

A integração respeita o contrato da `BaseScraper`, mantendo estritamente separada a I/O (rede) da lógica de Parse (transformação em memória).

1. **Autenticação (OAuth2)**:
   - Durante o estágio de extração de dados, a classe se comunica com a rota de tokens `https://api.mercadolibre.com/oauth/token`.
   - Utiliza-se o fluxo de concessão `client_credentials` enviando o `MERCADOLIVRE_APP_ID` e `MERCADOLIVRE_APP_SECRET_KEY`.
   - Um `access_token` válido é retornado para autorizar as consultas subsequentes.

2. **Extração de Dados via HTTP/2 (`fetch()`)**:
   - Em vez de realizar navegação gráfica de páginas, o método `fetch()` invoca o injetado `client.request` do Playwright (o módulo `APIRequestContext`). Isso reaproveita a camada de requisição assíncrona do projeto de forma eficiente.
   - O identificador único do produto do Mercado Livre (ex: `MLB53508354`) é extraído via regex diretamente da `product_url`.
   - O scraper consulta dois endpoints combinados:
     - **Catálogo (`/products/{id}`)**: Traz o status de disponibilidade do catálogo, nome da placa sem poluição SEO, e as fotos principais.
     - **Itens de Venda (`/products/{id}/items`)**: Traz as informações das ofertas (Anúncios) que alimentam aquele catálogo específico. Desse payload são retirados os valores à vista (`price_cash`), o cálculo dinâmico de juros das ofertas normais (`price_installments`), além do limite e parcelamento (`installment_count`).

3. **Parse Determinístico (`parse()`)**:
   - O método `parse()` não varre DOM ou HTML. Ele recebe os JSONs unificados e os valida construindo o `PriceContract` em memória.
   - É resistente a catálogos esgotados, capturando graciosamente a flag `is_available = False`.
   - No banco de dados (SQLite), o log dessa ferramenta fica gravado com a assinatura rastreável de `parser_version = "mercado-livre_api_v1"`.

## Configuração do Ambiente (Requisitos)

Para que a orquestração deste módulo seja executada com sucesso, é obrigatório preencher as credenciais de API no arquivo `.env` localizado na raiz do projeto (mesmo nível do `docker-compose.yml`):

```env
MERCADOLIVRE_APP_ID="<seu-app-id>"
MERCADOLIVRE_APP_SECRET_KEY="<seu-app-secret-key>"
```

Estas variáveis são carregadas nativamente pelo utilitário `src/core/config.py` e propagadas via a instância estática `settings`. Sem essas definições o scraper logará erros de autenticação na API.

## Referências
- [Mercado Livre Developers](https://developers.mercadolivre.com.br/)
- Repositório Principal de Documentação de Regras: `AGENTS.md`
