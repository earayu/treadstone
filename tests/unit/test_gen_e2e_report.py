"""Unit tests for scripts/gen-e2e-report.py (Hurl HTML post-processor)."""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "gen-e2e-report.py"


def _load_gen_e2e_report():
    spec = importlib.util.spec_from_file_location("gen_e2e_report", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_gen_e2e_report()
parse_rows = _mod.parse_rows
render = _mod.render
cluster_rows_into_runs = _mod.cluster_rows_into_runs


def _minimal_row(ts: int, short_name: str, href_suffix: str) -> dict:
    return {
        "timestamp": ts,
        "status": "success",
        "filename": f"tests/e2e/{short_name}",
        "short_name": short_name,
        "duration_ms": 100,
        "source_href": f"store/{href_suffix}-source.html",
        "timeline_href": f"store/{href_suffix}-timeline.html",
        "start_time": "-",
        "duration_s": "0.1",
    }


# Minimal Hurl 5.x-style index fragment (data-* on <tr>, links under store/)
_HURL_INDEX_ROW_STORE = """
<table><tbody>
<tr
  data-duration="100"
  data-status="success"
  data-filename="tests/e2e/01-auth-flow.hurl"
  data-id="08aad14a-8d10-4ecc-892e-a72703c5b494"
  data-timestamp="1696473444">
  <td><a href="store/08aad14a-8d10-4ecc-892e-a72703c5b494-source.html">01-auth-flow.hurl</a></td>
  <td><a href="store/08aad14a-8d10-4ecc-892e-a72703c5b494-timeline.html">success</a></td>
  <td>2023-10-05T02:37:24Z</td>
  <td>0.1s</td>
</tr>
</tbody></table>
"""

# Same row with bare UUID filenames (no store/ prefix)
_HURL_INDEX_ROW_BARE = """
<table><tbody>
<tr data-duration="200" data-status="failure" data-filename="tests/e2e/02-api-keys.hurl"
    data-id="a6641ae3-8ce0-4d9f-80c5-3e23e032e055" data-timestamp="1696473500">
  <td><a href="a6641ae3-8ce0-4d9f-80c5-3e23e032e055-source.html">02-api-keys.hurl</a></td>
  <td><a href="a6641ae3-8ce0-4d9f-80c5-3e23e032e055-timeline.html">failure</a></td>
  <td>-</td>
  <td>0.2s</td>
</tr>
</tbody></table>
"""


def test_parse_rows_store_hrefs() -> None:
    rows = parse_rows(_HURL_INDEX_ROW_STORE)
    assert len(rows) == 1
    r = rows[0]
    assert r["timestamp"] == 1696473444
    assert r["status"] == "success"
    assert r["source_href"] == "store/08aad14a-8d10-4ecc-892e-a72703c5b494-source.html"
    assert r["timeline_href"] == "store/08aad14a-8d10-4ecc-892e-a72703c5b494-timeline.html"
    assert r["short_name"] == "01-auth-flow.hurl"


def test_parse_rows_bare_uuid_hrefs() -> None:
    rows = parse_rows(_HURL_INDEX_ROW_BARE)
    assert len(rows) == 1
    r = rows[0]
    assert r["source_href"] == "a6641ae3-8ce0-4d9f-80c5-3e23e032e055-source.html"
    assert r["timeline_href"] == "a6641ae3-8ce0-4d9f-80c5-3e23e032e055-timeline.html"


def test_parse_rows_tr_without_attributes_still_matches() -> None:
    html = """
    <table><tbody>
    <tr>
      <td><a href="store/11111111-1111-1111-1111-111111111111-source.html">x.hurl</a></td>
      <td><a href="store/11111111-1111-1111-1111-111111111111-timeline.html">success</a></td>
      <td>t</td>
      <td>1s</td>
    </tr>
    </tbody></table>
    """
    rows = parse_rows(html)
    assert len(rows) == 1
    assert rows[0]["timestamp"] == 0
    assert "store/" in rows[0]["source_href"]


def test_parse_rows_skips_row_when_href_missing() -> None:
    bad = """
    <tr data-duration="1" data-status="success" data-filename="a.hurl"
        data-id="11111111-1111-1111-1111-111111111111" data-timestamp="1">
      <td>no link</td>
      <td><a href="store/11111111-1111-1111-1111-111111111111-timeline.html">success</a></td>
      <td>-</td>
      <td>0s</td>
    </tr>
    """
    assert parse_rows(bad) == []


def test_render_preserves_hrefs_in_output() -> None:
    rows = parse_rows(_HURL_INDEX_ROW_STORE)
    out = render(rows)
    assert 'href="store/08aad14a-8d10-4ecc-892e-a72703c5b494-source.html"' in out
    assert 'href="store/08aad14a-8d10-4ecc-892e-a72703c5b494-timeline.html"' in out
    assert "E2E Test Report" in out


@pytest.mark.parametrize(
    "snippet",
    [
        _HURL_INDEX_ROW_STORE,
        _HURL_INDEX_ROW_BARE,
    ],
)
def test_render_roundtrip_links_non_empty(snippet: str) -> None:
    rows = parse_rows(snippet)
    out = render(rows)
    for r in rows:
        assert f'href="{r["source_href"]}"' in out
        assert f'href="{r["timeline_href"]}"' in out


def test_cluster_rows_into_runs_merges_within_gap() -> None:
    rows = [
        _minimal_row(100, "a.hurl", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        _minimal_row(105, "b.hurl", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        _minimal_row(110, "c.hurl", "cccccccc-cccc-cccc-cccc-cccccccccccc"),
    ]
    runs = cluster_rows_into_runs(rows, 300)
    assert len(runs) == 1
    assert len(runs[0]) == 3


def test_cluster_rows_into_runs_splits_on_gap() -> None:
    rows = [
        _minimal_row(100, "a.hurl", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        _minimal_row(500, "b.hurl", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]
    runs = cluster_rows_into_runs(rows, 300)
    assert len(runs) == 2


def test_render_one_section_when_timestamps_clustered() -> None:
    rows = [
        _minimal_row(1000, "a.hurl", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        _minimal_row(1050, "b.hurl", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        _minimal_row(1100, "c.hurl", "cccccccc-cccc-cccc-cccc-cccccccccccc"),
    ]
    out = render(rows, gap_seconds=300)
    assert out.count('<section class="run ') == 1


def test_render_two_sections_when_gap_exceeded() -> None:
    rows = [
        _minimal_row(100, "a.hurl", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        _minimal_row(500, "b.hurl", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]
    out = render(rows, gap_seconds=300)
    assert out.count('<section class="run ') == 2
