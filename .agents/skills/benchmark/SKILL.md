---
name: benchmark
description: >-
  Use when tasks involve tests/benchmark/, sandbox burst load tests, the treadstone
  CLI against a remote API, scenario YAML under tests/benchmark/scenarios/, or
  artifacts run.json / events.jsonl / summary.json; also when debugging 429s,
  poll_timeout, ready stalls, auth failures, or leftover loadtest sandboxes.
---

# Treadstone benchmark harness

## What this is

[`tests/benchmark/`](../../../tests/benchmark/) is a **standalone** Python tool (not pytest) that shells out to the **`treadstone` CLI** (`--json`) to stress **sandbox create → poll-until-ready → delete**. Each run tags sandboxes with a deterministic label `loadtest:run-<run_id>`.

It exists for **manual or scripted** capacity experiments. **Do not** add it to `make test`, CI, or PR gates unless the team explicitly decides otherwise.

---

## Operator flow

1. Optional: copy [`benchmark.config.yaml.example`](../../../tests/benchmark/benchmark.config.yaml.example) → `tests/benchmark/benchmark.config.yaml` (gitignored).
2. Binary via [`lib/binary.py`](../../../tests/benchmark/lib/binary.py): `--binary` / `TREADSTONE_BINARY` → cache `tests/benchmark/.bin/` → else `install.sh`.
3. `python tests/benchmark/setup.py` — binary + `auth whoami` (fail fast).
4. `python tests/benchmark/runner.py <scenario.yaml>` — **create → poll → cleanup** (unless `--no-cleanup`).

---

## CLI quick reference

| Action | Command |
|--------|---------|
| Preflight | `python tests/benchmark/setup.py` |
| Run | `python tests/benchmark/runner.py tests/benchmark/scenarios/pilot_stateless.yaml` |
| Plan only | same + `--dry-run` (matrix expansion, no API calls) |
| Skip deletes | `--no-cleanup` (sandboxes keep label `loadtest:run-<run_id>`) |
| Pin binary | `--binary PATH` or `TREADSTONE_BINARY=PATH` |
| Pin server | `--base-url URL` or `TREADSTONE_BASE_URL` |

**`base_url` resolution (highest wins):** `--base-url` → `TREADSTONE_BASE_URL` → `benchmark.config.yaml` → `~/.config/treadstone/config.toml` (CLI default).

**`binary_version` resolution:** `--version` → `benchmark.config.yaml` → `"latest"`.

---

## Scenario file (YAML)

Validated by [`runner.load_scenario`](../../../tests/benchmark/runner.py):

| Field | Rule |
|-------|------|
| `name` | Required string |
| `matrix` | Non-empty list; each row needs `template`, integer `count` ≥ 1, optional `persist` (bool). If `persist: true`, **`storage_size` is required** |
| `concurrency` | Optional; default **10** (create + poll pool size) |
| `ready_timeout_sec` | Optional; default **900** |
| `poll_interval_sec` | Optional; default **10** |
| `auto_stop_interval` / `auto_delete_interval` | Passed through to `sandboxes create` (defaults 60 / -1) |

The parser is a **minimal subset** of YAML (no anchors, no complex merges) — keep scenarios simple.

**Matrix expansion:** each row’s `count` is repeated; every instance becomes one `CreateTask` with label `loadtest:run-<run_id>`.

**Cleanup (matches [`runner.py`](../../../tests/benchmark/runner.py) + [`executor.py`](../../../tests/benchmark/lib/executor.py)):** After poll, cleanup runs unless `--no-cleanup`. On **Ctrl+C**, cleanup is skipped only when `cleanup.on_failure` is **false** (default **true**); when true, interrupt still honors `--no-cleanup`. **`cleanup.after_run` in YAML is not read** by the runner.

**Deletes:** Same `persist` on every matrix row → `persist_filter` deletes only that kind; mixed persist rows → delete all with the run label. Cleanup tries `sandboxes list --label`; on failure, **full list (limit 1000)** + client-side match on `loadtest:<run_id>`.

---

## Artifacts

Each run writes under **`tests/benchmark/results/<run_id>/`** (gitignored):

| File | Contents |
|------|----------|
| `run.json` | Scenario snapshot, `run_label`, binary path, `base_url`, `treadstone_version`, machine, timestamps |
| `events.jsonl` | One JSON object per line: `create_*`, `ready`, `poll_timeout`, `failed_status`, `delete_*` |
| `summary.json` | Aggregates from `Reporter` (rates, latencies, error counts) — read this for pass/fail summaries |

---

## Guardrails

Large bursts on **prod** need approval. Do not commit **`results/`**, **`.bin/`**, or secret config. Auth failures: fix CLI login — **no** bypass.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| Auth exit | `treadstone auth login` or API key per CLI |
| 429 / `create_err` | Lower `concurrency`; check org limits |
| `poll_timeout` | Raise `ready_timeout_sec` or reduce load; check cluster readiness |
| Stray sandboxes | Manual `sandboxes list` + filter `loadtest`; fallback may miss if list truncated |
| YAML errors | Simple YAML only; no anchors |

Stub: [`tests/benchmark/README.md`](../../../tests/benchmark/README.md) → this file + `AGENTS.md`.
