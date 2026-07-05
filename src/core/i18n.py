import json
import os
from typing import Dict, Any

class I18n:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.locales = {}
            cls._instance.load_locales()
        return cls._instance
        
    def load_locales(self):
        """Loads all JSON translation files from data/locales/ into memory."""
        # Calculate absolute path to data/locales from this file (src/core/i18n.py)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        locales_dir = os.path.join(base_dir, "data", "locales")
        
        if not os.path.exists(locales_dir):
            return
            
        for filename in os.listdir(locales_dir):
            if filename.endswith(".json"):
                lang_code = filename.replace(".json", "")
                with open(os.path.join(locales_dir, filename), "r", encoding="utf-8") as f:
                    self.locales[lang_code] = json.load(f)
                    
    def t(self, key: str, lang: str = "pt_BR", **kwargs) -> str:
        """
        Translates a key into the specified language.
        If the language or key is missing, it falls back to pt_BR, then to the key itself.
        Supports standard Python string formatting via kwargs.
        """
        # Map UI selector strings to internal locale codes
        if lang == "pt-BR":
            lang = "pt_BR"
        elif lang == "en-US":
            lang = "en_US"
            
        lang_dict = self.locales.get(lang, self.locales.get("pt_BR", {}))
        text = lang_dict.get(key, key)
        
        if kwargs and text != key:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text

# Export a singleton instance and a bound translation function for easy importing
i18n = I18n()
t = i18n.t
