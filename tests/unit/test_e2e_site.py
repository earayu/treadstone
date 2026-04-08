"""Unit tests for scripts/e2e_site.py."""

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "e2e_site.py"


def _load():
    spec = importlib.util.spec_from_file_location("e2e_site", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load()
merge_batch = _mod.merge_batch
discover_batches = _mod.discover_batches
_batch_sort_key = _mod._batch_sort_key


def test_batch_sort_key_orders_newest_run_id_first() -> None:
    assert _batch_sort_key("100-2") > _batch_sort_key("99-1")
    assert _batch_sort_key("24133439920-1") > _batch_sort_key("24133439919-9")


def test_merge_batch_copies_and_renders_index(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "index.html").write_text("<!DOCTYPE html><html><body>ok</body></html>", encoding="utf-8")
    (incoming / "store").mkdir()
    (incoming / "store" / "x.html").write_text("x", encoding="utf-8")
    (incoming / "batch-meta.json").write_text(
        json.dumps({"schema": 1, "passed": 3, "failed": 0, "hurl_files": 3}),
        encoding="utf-8",
    )

    site = tmp_path / "site"
    merge_batch(incoming=incoming, site_root=site, batch_id="999-1")

    assert (site / "e2e" / "batches" / "999-1" / "index.html").read_text(encoding="utf-8") == (
        incoming / "index.html"
    ).read_text(encoding="utf-8")
    assert (site / "e2e" / "batches" / "999-1" / "store" / "x.html").exists()
    landing = (site / "e2e" / "index.html").read_text(encoding="utf-8")
    assert "999-1" in landing
    assert "./batches/999-1/index.html" in landing
    assert (site / "index.html").exists()
    assert (site / ".nojekyll").exists()


def test_discover_batches_newest_first(tmp_path: Path) -> None:
    site = tmp_path / "site"
    for bid in ("10-1", "20-1"):
        d = site / "e2e" / "batches" / bid
        d.mkdir(parents=True)
        (d / "index.html").write_text("h", encoding="utf-8")
    found = discover_batches(site)
    assert [x[0] for x in found] == ["20-1", "10-1"]


def test_merge_batch_replaces_existing_batch(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "index.html").write_text("<html>a</html>", encoding="utf-8")
    site = tmp_path / "site"
    merge_batch(incoming=incoming, site_root=site, batch_id="1-1")
    (incoming / "index.html").write_text("<html>b</html>", encoding="utf-8")
    merge_batch(incoming=incoming, site_root=site, batch_id="1-1")
    assert "b</html>" in (site / "e2e" / "batches" / "1-1" / "index.html").read_text(encoding="utf-8")
