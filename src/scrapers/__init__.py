"""
Scraper implementations. Importing this package auto-imports every module
inside it, so each module's @register_scraper-decorated class self-registers
without needing to be named individually anywhere else (e.g. main.py).
"""

import importlib
import pkgutil

for _module_info in pkgutil.iter_modules(__path__, prefix=f"{__name__}."):
    importlib.import_module(_module_info.name)
