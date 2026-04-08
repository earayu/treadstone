#!/usr/bin/env python3
"""
Merge one E2E HTML report directory into a GitHub Pages site layout with historical batches.

Layout (site root = gh-pages branch checkout):

  e2e/index.html              — dashboard listing all batches
  e2e/batches/<batch_id>/     — one directory per workflow run (index.html + store/ + batch-meta.json)
  index.html                  — minimal entry linking to e2e/
  .nojekyll

Usage:
  python scripts/e2e_site.py merge --incoming DIR --site-root DIR --batch-id ID

Env (optional, for batch-meta augmentation in CI):
  GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_SERVER_URL, GITHUB_WORKFLOW
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

_BATCH_META = "batch-meta.json"

# Shared look with gen-e2e-report.py (subset for dashboard)
_LANDING_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #f8f9fb; --surface: #ffffff; --border: #e2e5eb; --text: #1a1d23;
  --text-muted: #6b7280; --accent: #6366f1; --pass: #16a34a; --fail: #dc2626;
  --shadow: 0 1px 3px rgba(0,0,0,.08); --radius: 10px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --mono: "SF Mono", "Fira Code", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2d3142; --text: #e2e4ec;
    --text-muted: #8b93a8; --pass: #4ade80; --fail: #f87171;
    --shadow: 0 1px 3px rgba(0,0,0,.4);
  }
}
body {
  font-family: var(--font); font-size: 14px; line-height: 1.5;
  background: var(--bg); color: var(--text); min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1100px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.lead { color: var(--text-muted); margin-bottom: 28px; font-size: 15px; }
.table-wrap {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow); overflow-x: auto;
}
table { width: 100%; border-collapse: collapse; }
th {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .07em;
  color: var(--text-muted); padding: 10px 14px; text-align: left;
  border-bottom: 1px solid var(--border); background: var(--bg);
}
td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: rgba(0,0,0,.015); }
@media (prefers-color-scheme: dark) { tbody tr:hover { background: rgba(255,255,255,.03); } }
.mono { font-family: var(--mono); font-size: 13px; }
.badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 99px; }
.badge-pass { background: rgba(22,163,74,.15); color: var(--pass); }
.badge-fail { background: rgba(220,38,38,.15); color: var(--fail); }
"""


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def augment_batch_meta(batch_dir: Path) -> None:
    """Merge CI env into batch-meta.json when present."""
    meta_path = batch_dir / _BATCH_META
    if meta_path.exists():
        data: dict = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        data = {"schema": 1}

    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    rid = os.environ.get("GITHUB_RUN_ID")
    if rid:
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        data["github"] = {
            "run_id": int(rid),
            "run_attempt": int(attempt) if attempt.isdigit() else 1,
            "repository": repo,
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "run_url": f"{server}/{repo}/actions/runs/{rid}" if repo else "",
        }

    sha = os.environ.get("GITHUB_SHA", "")
    if sha:
        data["git"] = {
            "sha": sha,
            "sha_short": sha[:7],
            "ref_name": os.environ.get("GITHUB_REF_NAME", ""),
            "commit_url": f"{server}/{repo}/commit/{sha}" if repo else "",
        }

    pr_number = os.environ.get("PR_NUMBER", "")
    pr_url = os.environ.get("PR_URL", "")
    if pr_number:
        data["pr"] = {
            "number": int(pr_number) if pr_number.isdigit() else pr_number,
            "url": pr_url,
        }

    data["published_at"] = _utc_now_iso()
    meta_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _batch_sort_key(batch_id: str) -> tuple[int, int]:
    """Sort newest GitHub run first: batch_id is run_id-run_attempt."""
    m = re.match(r"^(\d+)-(\d+)$", batch_id)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m2 = re.match(r"^(\d+)$", batch_id)
    if m2:
        return (int(m2.group(1)), 0)
    return (0, 0)


def discover_batches(site_root: Path) -> list[tuple[str, Path]]:
    batches_dir = site_root / "e2e" / "batches"
    if not batches_dir.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(batches_dir.iterdir(), key=lambda x: _batch_sort_key(x.name), reverse=True):
        if p.is_dir() and (p / "index.html").is_file():
            out.append((p.name, p))
    return out


def render_e2e_index(site_root: Path) -> None:
    batches = discover_batches(site_root)
    rows_html: list[str] = []
    for batch_id, batch_path in batches:
        meta_path = batch_path / _BATCH_META
        published = "—"
        result = None
        run_link = ""
        git_cell = "—"
        pr_cell = "—"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                published = meta.get("published_at", published)
                result = meta.get("result")
                gh = meta.get("github") or {}
                run_link = gh.get("run_url") or ""
                git = meta.get("git") or {}
                sha_short = git.get("sha_short", "")
                commit_url = git.get("commit_url", "")
                ref_name = git.get("ref_name", "")
                if sha_short and commit_url:
                    git_cell = f'<a href="{commit_url}" rel="noopener" class="mono">{sha_short}</a>'
                    if ref_name:
                        git_cell += f' <span style="color:var(--text-muted);font-size:12px">{ref_name}</span>'
                elif ref_name:
                    git_cell = f'<span class="mono">{ref_name}</span>'
                pr = meta.get("pr") or {}
                pr_number = pr.get("number")
                pr_url = pr.get("url", "")
                if pr_number and pr_url:
                    pr_cell = f'<a href="{pr_url}" rel="noopener">#{pr_number}</a>'
                elif pr_number:
                    pr_cell = f"#{pr_number}"
            except json.JSONDecodeError:
                pass

        if result == "pass":
            result_cell = '<span class="badge badge-pass">pass</span>'
        elif result == "fail":
            result_cell = '<span class="badge badge-fail">fail</span>'
        else:
            result_cell = "—"

        batch_href = f"./batches/{batch_id}/index.html"
        gh_cell = f'<a href="{run_link}" rel="noopener">CI run</a>' if run_link else "—"

        rows_html.append(
            f"""<tr>
  <td>{published}</td>
  <td>{git_cell}</td>
  <td>{pr_cell}</td>
  <td>{result_cell}</td>
  <td>{gh_cell}</td>
  <td><a href="{batch_href}">Report</a></td>
</tr>"""
        )

    body = "\n".join(rows_html) if rows_html else '<tr><td colspan="6">No batches yet.</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>K8s E2E reports</title>
  <style>{_LANDING_CSS}</style>
</head>
<body>
<div class="container">
  <h1>K8s E2E reports</h1>
  <p class="lead">One row per workflow run — click Report to open the Hurl HTML detail page.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Time (UTC)</th>
          <th>Git</th>
          <th>PR</th>
          <th>Result</th>
          <th>CI</th>
          <th>Report</th>
        </tr>
      </thead>
      <tbody>
{body}
      </tbody>
    </table>
  </div>
  <p class="lead" style="margin-top:24px"><a href="../">← Repository home (Pages root)</a></p>
</div>
</body>
</html>
"""
    out = site_root / "e2e" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def render_root_index(site_root: Path) -> None:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Treadstone — CI reports</title>
  <style>{_LANDING_CSS}</style>
</head>
<body>
<div class="container">
  <h1>Treadstone</h1>
  <p class="lead"><a href="e2e/">K8s E2E test reports (batches)</a></p>
</div>
</body>
</html>
"""
    (site_root / "index.html").write_text(html, encoding="utf-8")
    (site_root / ".nojekyll").touch()


def merge_batch(*, incoming: Path, site_root: Path, batch_id: str) -> None:
    if not incoming.is_dir():
        raise SystemExit(f"incoming directory not found: {incoming}")
    if not (incoming / "index.html").is_file():
        raise SystemExit(f"missing {incoming}/index.html")
    dest = site_root / "e2e" / "batches" / batch_id
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(incoming, dest)
    augment_batch_meta(dest)
    render_e2e_index(site_root)
    render_root_index(site_root)


def main() -> None:
    ap = argparse.ArgumentParser(description="E2E GitHub Pages site merge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge", help="Copy one report dir into site and regenerate indexes")
    m.add_argument("--incoming", type=Path, required=True, help="reports/e2e after Hurl + gen-e2e-report")
    m.add_argument("--site-root", type=Path, required=True, help="gh-pages checkout root")
    m.add_argument("--batch-id", required=True, help="Unique id, e.g. ${{ github.run_id }}-${{ github.run_attempt }}")

    args = ap.parse_args()
    if args.cmd == "merge":
        merge_batch(incoming=args.incoming, site_root=args.site_root, batch_id=args.batch_id)


if __name__ == "__main__":
    main()
