# Documentação: Mercado Livre Scraper

O scraper do Mercado Livre (`MercadoLivreScraper`) foi construído com uma arquitetura diferenciada em relação aos demais (como Kabum e Terabyte). Devido às rigorosas proteções anti-bot (Cloudflare/Datadome) presentes nas Lojas Oficiais do Mercado Livre, a navegação via DOM (Playwright) foi substituída por uma integração nativa e 100% resiliente utilizando a **API Oficial do Mercado Livre**.

## 🏗️ Arquitetura de Integração

O Scraper atua como um parceiro VIP ("App" do Mercado Livre), utilizando credenciais OAuth 2.0 para consultar os bancos de dados do e-commerce diretamente.

### 1. Autenticação Automática (`client_credentials`)
O scraper gerencia de forma autônoma o ciclo de vida do token de acesso:
- Ele consome `APP_ID` e `SECRET_KEY` diretamente das variáveis de ambiente ou do arquivo `.env` (mapeado via `config.toml` -> `AppSettings`).
- Realiza uma requisição `POST` para `https://api.mercadolibre.com/oauth/token` sempre que o scraper é inicializado ou quando o token expira (tempo de vida de 6 horas).
- O `Bearer Token` obtido é anexado no header `Authorization` de todas as chamadas subsequentes.

### 2. Bypass de Defesas e Performance
Como consumimos a API Oficial, a execução ocorre em **milissegundos** e **nunca** é bloqueada por desafios de Captcha, testes de Javascript ou fingerprinting biométrico, garantindo 100% de precisão nos preços reportados.

### 3. Rotas Dinâmicas de Catálogo vs. Anúncio
A arquitetura do scraper foi desenvolvida para suportar automaticamente os dois padrões de URLs do Mercado Livre:

* **Padrão Produto/Catálogo (ex: `/p/MLB12345`)**: O scraper identifica o `id_type = product`. Como o catálogo possui múltiplos vendedores, ele consulta a rota de `/products/{id}/items` para varrer todas as listagens ativas e seleciona, com precisão cirúrgica, **o menor preço disponível daquele modelo exato**, não dependendo apenas da Buy Box principal.
* **Padrão Item (ex: `/MLB-12345-nome`)**: O scraper identifica o `id_type = item` e consome diretamente a rota `/items/{id}`, que retorna o preço em tempo real de um anúncio individual.

### 4. Mapeamento Inteligente de Parcelamento
As listagens do Mercado Livre possuem tipos (`listing_type_id`). Através de engenharia reversa das regras de negócio:
- O Scraper mapeia as flags para descobrir o preço parcelado sem consultar rotas complexas de calculadora.
- Listagens **Premium/Ouro (`gold_pro`)** garantem parcelamento em até 10x sem juros (ou seja, Preço à Prazo = Preço à Vista). 
- Demais listagens (clássicas) sinalizam ausência de parcelamento sem juros e não misturam seus valores nas estatísticas do Orchestrator.

---

## 🚀 Configuração

Para que o Scraper do Mercado Livre funcione, você DEVE possuir uma conta de Desenvolvedor no Mercado Livre e registrar uma aplicação para obter o `MERCADOLIVRE_APP_ID` e `MERCADOLIVRE_APP_SECRET_KEY`.

1. Acesse o [Portal de Desenvolvedores do Mercado Livre](https://developers.mercadolivre.com.br/).
2. Crie uma aplicação (Não requer permissões especiais, apenas leitura anônima de itens de catálogo).
3. Insira suas credenciais no arquivo `.env` da raiz do projeto:

```env
MERCADOLIVRE_APP_ID=seu_app_id
MERCADOLIVRE_APP_SECRET_KEY=sua_secret_key_longa_aqui
```

4. Suba a aplicação via Docker (`docker-compose up -d --build`). O `docker-compose.yml` já está configurado para injetar este arquivo `.env` nos containers do Orquestrador e da Dashboard.

> [!WARNING]
> Sem estas variáveis, o `MercadoLivreScraper` não conseguirá gerar o Token OAuth e **falhará silenciosamente** para todos os links do Mercado Livre cadastrados.

## 🧪 Testes Unitários

O `MercadoLivreScraper` foi abstraído para separar a fase de requisição HTTP (onde ocorre o OAuth e a montagem das rotas) da fase de Parsing (extração de dados).

Os testes encontram-se em `tests/unit/test_mercadolivre_parser.py` e utilizam *fixtures* JSON (que imitam a API Oficial) em vez do código HTML padrão usado pelas outras lojas. Apenas garanta que o formato de testes injete o dicionário com a chave `"data"` conforme o contrato retornado pela função `fetch` customizada do Scraper.
