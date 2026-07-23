import importlib
import pkgutil

# Auto-import all spider implementations in this package so their @register_spider decorators run on boot
for _, module_name, _ in pkgutil.walk_packages(__path__, prefix=__name__ + "."):
    if module_name != __name__ + ".registry" and module_name != __name__ + ".base_spider":
        importlib.import_module(module_name)
