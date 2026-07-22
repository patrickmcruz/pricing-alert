# Initiative Spec: Pluggable Store Spiders for Automated Multi-Category Hardware Discovery

## Executive Summary
This initiative introduces a pluggable, decoupled `src/spiders/` discovery module for automated hardware discovery across Brazilian e-commerce stores (starting with **CPUs / Processors**, expandable to GPUs, RAM, Motherboards, and SSDs). Store spiders run on demand or low-frequency schedules, exploring search grids/APIs to populate the catalog and `listings` table, while `src/scrapers/` continue high-frequency price history monitoring.

---

## 1. Problem Statement
Single-product scrapers in `src/scrapers/` require known product URLs. Previously, discovering new hardware listings relied on manual script execution (`scripts/discover_pichau_gpus.py`). As the system expands beyond GPUs to CPUs (AMD Ryzen 5000/7000/9000, Intel Core 12ª/13ª/14ª/Ultra) and other hardware categories, manual discovery becomes unsustainable.

---

## 2. Technical Architecture & Component Boundaries

### Component Responsibilities:
- **`src/spiders/` (Low Frequency / On-Demand Discovery):**
  - Explores store search grids or search APIs (e.g. Mercado Livre REST search API, Pichau GraphQL/RSC payload).
  - Returns normalized `DiscoveredSKU` objects.
- **`TitleParserRegistry` (Normalization):**
  - Parses unstructured raw titles into typed spec models (`CPUSpecs`, `GPUSpecs`, `RAMSpecs`, `MotherboardSpecs`).
- **`DiscoveryEngine` (Persistence & Orchestration):**
  - Idempotently upserts discovered items into `categories`, `products`, `listings`, and `target_urls` PostgreSQL tables.
- **`src/scrapers/` (High Frequency Price Tracking):**
  - Visited pages on target URLs, tracking price observations over time.

---

## 3. Data Contracts (Pydantic v2)

### `DiscoveredSKU`:
- `store_name: str`
- `search_keyword: str`
- `product_url: str`
- `product_title: str`
- `brand: str | None = None`
- `model: str | None = None`
- `category: str = "cpu"`

### `CPUSpecs`:
- `socket: str` (e.g., "AM5", "AM4", "LGA1851", "LGA1700")
- `cores: int | None = None`
- `threads: int | None = None`
- `base_clock_ghz: float | None = None`
- `boost_clock_ghz: float | None = None`
- `has_integrated_gpu: bool = False`
- `tdp_w: int | None = None`
