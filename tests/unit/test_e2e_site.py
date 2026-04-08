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
augment_batch_meta = _mod.augment_batch_meta
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
        json.dumps({"schema": 1, "result": "pass"}),
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
    assert "pass" in landing
    assert (site / "index.html").exists()
    assert (site / ".nojekyll").exists()


def test_merge_batch_fail_result_shows_in_index(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "index.html").write_text("<html><body>fail run</body></html>", encoding="utf-8")
    (incoming / "batch-meta.json").write_text(
        json.dumps({"schema": 1, "result": "fail"}),
        encoding="utf-8",
    )

    site = tmp_path / "site"
    merge_batch(incoming=incoming, site_root=site, batch_id="42-1")

    landing = (site / "e2e" / "index.html").read_text(encoding="utf-8")
    assert "fail" in landing
    assert "badge-fail" in landing


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


def test_augment_batch_meta_git_pr(tmp_path: Path, monkeypatch) -> None:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    (batch_dir / "batch-meta.json").write_text(
        json.dumps({"schema": 1, "result": "pass"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("GITHUB_SHA", "abc1234567890")
    monkeypatch.setenv("GITHUB_REF_NAME", "feat/my-branch")
    monkeypatch.setenv("GITHUB_RUN_ID", "9999")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_WORKFLOW", "K8s E2E")
    monkeypatch.setenv("PR_NUMBER", "42")
    monkeypatch.setenv("PR_URL", "https://github.com/owner/repo/pull/42")

    augment_batch_meta(batch_dir)

    meta = json.loads((batch_dir / "batch-meta.json").read_text(encoding="utf-8"))

    assert meta["git"]["sha"] == "abc1234567890"
    assert meta["git"]["sha_short"] == "abc1234"
    assert meta["git"]["ref_name"] == "feat/my-branch"
    assert "abc1234567890" in meta["git"]["commit_url"]

    assert meta["pr"]["number"] == 42
    assert meta["pr"]["url"] == "https://github.com/owner/repo/pull/42"

    assert meta["github"]["run_id"] == 9999
    assert "published_at" in meta


def test_augment_batch_meta_no_pr(tmp_path: Path, monkeypatch) -> None:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()

    monkeypatch.setenv("GITHUB_SHA", "deadbeef1234")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.delenv("PR_NUMBER", raising=False)
    monkeypatch.delenv("PR_URL", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)

    augment_batch_meta(batch_dir)

    meta = json.loads((batch_dir / "batch-meta.json").read_text(encoding="utf-8"))
    assert meta["git"]["sha_short"] == "deadbee"
    assert "pr" not in meta


def test_render_e2e_index_shows_git_and_pr(tmp_path: Path, monkeypatch) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (incoming / "batch-meta.json").write_text(
        json.dumps({"schema": 1, "result": "pass"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("GITHUB_SHA", "cafebabe9876")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("PR_NUMBER", "7")
    monkeypatch.setenv("PR_URL", "https://github.com/owner/repo/pull/7")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)

    site = tmp_path / "site"
    merge_batch(incoming=incoming, site_root=site, batch_id="500-1")

    landing = (site / "e2e" / "index.html").read_text(encoding="utf-8")
    assert "cafebab" in landing
    assert "#7" in landing
    assert "pull/7" in landing
    assert "main" in landing
