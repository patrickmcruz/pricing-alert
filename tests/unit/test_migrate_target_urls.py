"""
Tests _load_json_manifest() - the one piece of scripts/migrate_target_urls.py
that's pure enough to unit test without a real database (the rest of the
script is DB/backup orchestration, same as scripts/discover_pichau_gpus.py's
discover(), and isn't unit-tested for the same reason). Confirms the legacy
JSON -> TargetUrlEntry mapping (see specs/target-urls-table/spec.md) handles
both a fully-populated row and one missing the optional fields entirely,
and that a missing file degrades to an empty list instead of raising.
"""
import json

from src.core.config import settings
from scripts.migrate_target_urls import _load_json_manifest


def test_load_json_manifest_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "target_urls_path", str(tmp_path / "does_not_exist.json"))

    assert _load_json_manifest() == []


def test_load_json_manifest_maps_rows_to_target_url_entries(tmp_path, monkeypatch):
    manifest_path = tmp_path / "target_urls.json"
    manifest_path.write_text(
        json.dumps([
            {
                "store_name": "kabum",
                "search_keyword": "rtx 5070",
                "product_url": "https://www.kabum.com.br/produto/123",
                "brand": "MSI",
                "model": "Shadow 2X OC",
                "product_title": "Placa de Video MSI RTX 5070",
            },
            {
                # A row missing every optional key entirely (not just null) -
                # confirms .get() is used rather than direct indexing.
                "store_name": "terabyte",
                "search_keyword": "rtx 5070 ti",
                "product_url": "https://www.terabyteshop.com.br/produto/456",
            },
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "target_urls_path", str(manifest_path))

    entries = _load_json_manifest()

    assert len(entries) == 2
    assert entries[0].store_name == "kabum"
    assert entries[0].brand == "MSI"
    assert entries[0].model == "Shadow 2X OC"
    assert entries[1].store_name == "terabyte"
    assert entries[1].brand is None
    assert entries[1].model is None
    assert entries[1].product_title is None
