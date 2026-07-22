# Modelo de Dados & Diagramas ER (MER / DER) 🗄️

Esta documentação apresenta o **Modelo Entidade-Relacionamento (MER)** conceitual e o **Diagrama de Entidade-Relacionamento (DER)** físico da base de dados PostgreSQL do ecossistema **GPU Price Tracker**.

---

## 1. Modelo Entidade-Relacionamento (MER - Conceitual)

### Entidades e Definições

1. **Categoria (`categories`)**: Representa a classe genérica do produto no catálogo (ex: `GPU`, `Placa Mãe`, `Memória RAM`). Suporta hierarquia auto-referenciada (`parent_id`).
2. **Marca (`brands`)**: Fabricante ou marca parceira de montagem (ex: `ASUS`, `MSI`, `Gigabyte`, `Corsair`).
3. **Chipset (`chipsets`)**: Processador gráfico ou Soquete/Chipset lógico padronizado (ex: `RTX 5070 Ti`, `RX 7900 XT`, `AM5`, `B650`).
4. **Produto (`products`)**: O item de catálogo normalizado e unificado. Combina uma Marca, uma Categoria, um Modelo limpo, atributos fixos (`mpn`, `product_line`, `is_oc`) e atributos dinâmicos em `specs` (JSONB).
5. **Loja (`stores`)**: Varejista de e-commerce monitorado (ex: `Pichau`, `KaBuM!`, `Terabyte`, `Mercado Livre`, `Amazon`).
6. **Anúncio (`listings`)**: A oferta específica de um produto em uma loja, vinculada por uma URL única. Mantém o título bruto (`product_title`) como histórico de auditoria.
7. **Execução de Scraper (`scraper_runs`)**: Registro da rodada de scraping de uma loja em um momento no tempo.
8. **Execução de Anúncio (`listing_runs`)**: Telemetria individual da tentativa de extração de cada anúncio.
9. **Observação de Preço (`price_observations`)**: O registro temporal (histórico) do preço capturado (à vista, parcelado, desconto, disponibilidade).
10. **Regra de Alerta (`alert_rules`)**: Regras personalizadas de notificação atreladas a um produto ou termo de busca.
11. **Evento de Alerta (`alert_events`)**: Disparos de alerta gerados quando uma observação de preço atende aos critérios de uma regra.

---

## 2. Diagrama de Entidade-Relacionamento (DER - Físico)

```mermaid
erDiagram
    categories ||--o{ categories : "parent"
    categories ||--o{ products : "classifica"
    brands ||--o{ products : "fabrica"
    chipsets ||--o{ products : "equipado com"
    products ||--o{ listings : "anunciado em"
    stores ||--o{ listings : "pertence a"
    stores ||--o{ scraper_runs : "executa rodada"
    scraper_runs ||--o{ listing_runs : "detalha tentativas"
    listings ||--o{ listing_runs : "registra tentativa"
    listings ||--o{ price_observations : "registra historico"
    scraper_runs ||--o{ price_observations : "origina"
    stores ||--o{ alert_rules : "filtra por"
    products ||--o{ alert_rules : "monitora"
    alert_rules ||--o{ alert_events : "dispara"
    price_observations ||--o{ alert_events : "causado por"

    categories {
        uuid id PK
        string name
        string slug UK
        uuid parent_id FK
        timestamp created_at
    }

    brands {
        uuid id PK
        string name UK
        timestamp created_at
    }

    chipsets {
        uuid id PK
        string maker
        string family
        string model UK
    }

    products {
        uuid id PK
        uuid brand_id FK
        uuid category_id FK
        string name
        string mpn UK
        string product_line
        boolean is_oc
        string gtin UK
        jsonb specs
        timestamp created_at
    }

    stores {
        uuid id PK
        string slug UK
        string display_name
        string base_url
        boolean is_active
        timestamp created_at
    }

    listings {
        uuid id PK
        uuid store_id FK
        uuid product_id FK
        string product_url UK
        string product_title
        string search_keyword
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    scraper_runs {
        uuid id PK
        uuid store_id FK
        string status
        timestamp started_at
        timestamp finished_at
        int listings_total
        int listings_succeeded
        int listings_failed
        string error_message
    }

    listing_runs {
        uuid id PK
        uuid scraper_run_id FK
        uuid listing_id FK
        string product_url
        string product_title
        string status
        timestamp started_at
        timestamp finished_at
        string error_message
    }

    price_observations {
        uuid id PK
        uuid listing_id FK
        uuid scraper_run_id FK
        decimal price_cash
        decimal price_installments
        int installment_count
        string currency
        decimal discount
        boolean is_available
        string parser_version
        timestamp scraped_at
    }

    alert_rules {
        uuid id PK
        uuid store_id FK
        uuid product_id FK
        string search_keyword
        string threshold_type
        decimal threshold_value
        boolean is_active
        timestamp created_at
    }

    alert_events {
        bigint id PK
        uuid alert_rule_id FK
        uuid price_observation_id FK
        string reason
        timestamp triggered_at
    }
```

---

## 3. Dicionário de Dados Completo

### Tabela `products`
| Coluna | Tipo | Restrições | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Identificador único global do produto. |
| `brand_id` | `UUID` | `NOT NULL, FK(brands.id)` | Marca/Fabricante (ex: Gigabyte, MSI). |
| `category_id` | `UUID` | `NOT NULL, FK(categories.id)` | Categoria (ex: GPU, Placa Mãe, RAM). |
| `name` | `TEXT` | `NOT NULL` | Nome limpo/modelo comercial do produto. |
| `mpn` | `TEXT` | `UNIQUE, NULLABLE` | Manufacturer Part Number (SKU da fábrica). |
| `product_line` | `TEXT` | `NULLABLE` | Linha de produto/sistema de refrigeração (ex: Windforce, TUF). |
| `is_oc` | `BOOLEAN` | `NOT NULL, DEFAULT false` | Indica se possui overclock de fábrica. |
| `gtin` | `TEXT` | `UNIQUE, NULLABLE` | Código EAN/UPC global do produto. |
| `specs` | `JSONB` | `NOT NULL, DEFAULT '{}'` | Atributos estendidos e indexados (GIN). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Timestamp UTC da criação do registro. |

---

## 4. Schemas dos Atributos Dinâmicos (`specs` JSONB)

Os atributos específicos de cada categoria de hardware são armazenados de forma indexada no campo `specs` (JSONB):

### 🎮 Categoria: Placa de Vídeo (`GPUSpecs`)
```json
{
  "chipset": "RTX 5070 Ti",
  "chip_maker": "NVIDIA",
  "vram_gb": 16,
  "vram_type": "GDDR7",
  "is_oc": true,
  "form_factor": "SFF",
  "product_line": "Windforce",
  "mpn": "GV-N507TWF3OC-16GD",
  "features": ["DLSS", "Ray Tracing"]
}
```

### 📟 Categoria: Placa Mãe (`MotherboardSpecs`)
```json
{
  "socket": "AM5",
  "chipset": "B650M",
  "form_factor": "Micro-ATX",
  "memory_type": "DDR5",
  "memory_slots": 4,
  "max_memory_gb": 192,
  "product_line": "TUF Gaming"
}
```

### ⚡ Categoria: Memória RAM (`RAMSpecs`)
```json
{
  "capacity_gb": 32,
  "module_count": 2,
  "memory_type": "DDR5",
  "speed_mhz": 6000,
  "latency_cl": "CL30",
  "has_rgb": true,
  "product_line": "Vengeance"
}
```
