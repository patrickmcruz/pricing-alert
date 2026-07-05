# Goal: Internationalization (i18n) Strategy

The goal is to implement a robust, lightweight internationalization system for the dashboard. The primary language will be **Portuguese (pt-BR)**, with **English (en-US)** as a secondary option. The user will be able to toggle the language directly from the Streamlit sidebar.

## Strategy & Architecture

Given the project's preference for clean, decoupled architecture, we will implement a dictionary-based translation system using JSON files. This avoids the complexity of compiling `gettext` `.mo` files while remaining incredibly fast and easy to maintain.

### 1. Locale Files (JSON)
We will create a new directory `data/locales/` to store our language dictionaries:
- `data/locales/pt_BR.json` (Default)
- `data/locales/en_US.json`

These files will contain key-value pairs. Example:
```json
{
  "sidebar_title": "Filtros",
  "market_overview": "🌐 Visão Geral do Mercado",
  "best_deal": "🏆 Melhor Oferta Agora"
}
```

### 2. The Translation Service (`src/core/i18n.py`)
We will build a lightweight `I18n` singleton class in `src/core/i18n.py`. 
- It will load the JSON files into memory once on startup.
- It will expose a standard translation function, typically `t(key, **kwargs)`, which supports string interpolation (e.g., `t("price_label", price=100)`).

### 3. Streamlit Integration (`src/ui/dashboard.py`)
- We will add a language selector in the sidebar: `st.sidebar.selectbox("Idioma / Language", ["pt-BR", "en-US"])`.
- The selected language will be saved in `st.session_state` so it persists during reruns.
- We will refactor all hardcoded strings in `dashboard.py` (e.g., "Current Market Overview", "Best Deal Right Now", "Price Trends") to use the `t()` function.

## Proposed Changes

### [NEW] `data/locales/pt_BR.json`
Contains all Portuguese translations (Primary).

### [NEW] `data/locales/en_US.json`
Contains all English translations (Secondary).

### [NEW] `src/core/i18n.py`
A lightweight translator class exposing `load_locales()` and `get_translation(lang, key)`.

### [MODIFY] `src/ui/dashboard.py`
1. Inject the `st.selectbox` for language selection at the top of the sidebar.
2. Replace all hardcoded strings with `t(key)` calls.

## User Review Required

> [!TIP]
> This strategy uses a custom JSON-based approach which is standard for Streamlit apps. It keeps dependencies at zero and is extremely easy to edit.
> If you meant you wanted to use a specific Python library (like the `python-i18n` package from pip), let me know and I can adapt the plan! Otherwise, this custom JSON approach is the cleanest fit for our architecture. Let me know if you approve!
