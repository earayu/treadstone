# CLI Guide

The `treadstone` CLI is how you drive the control plane from a terminal. This page covers **installation** and **how the tool behaves** — global flags, credentials, `--json`, `--help`, the optional `skills` commands, and defaults when you omit a subcommand.

Sandbox workflows, auth, API keys, and browser handoff are documented under **Core Workflows** and **Integrate**. For a **tabular list of every command**, see [CLI Reference](/docs/cli-reference.md).

## Install

```bash
# macOS / Linux:
curl -fsSL https://treadstone-ai.dev/install.sh | sh
# Windows (PowerShell):
irm https://treadstone-ai.dev/install.ps1 | iex
# pip
pip install treadstone-cli
# then
treadstone --help
treadstone --version
```

## Core CLI behavior

### Global options (root command)

These flags appear **before** the subcommand. They change how every invocation talks to the API and how output is formatted:

| Option | Purpose |
|--------|---------|
| `--json` | Print **structured JSON** instead of human-oriented tables and sentences. Use this whenever a script, agent, or CI job parses the result. |
| `--api-key` | Supply an API key for **this run only**. Same effect as the `TREADSTONE_API_KEY` environment variable for that process. |
| `--base-url` | Point the CLI at a specific control-plane URL (hosted cloud, self-hosted, or local dev). Overrides `TREADSTONE_BASE_URL` for that process when set. |
| `--version` | Print the CLI version and exit (no API call). |

`--help` is available on the root command and on every group and subcommand; it is not listed in the table because it is added automatically by the CLI framework.

### Credential precedence

Commands that need authentication resolve credentials in this order (highest priority first):

1. `--api-key` flag
2. `TREADSTONE_API_KEY` environment variable
3. Saved `api_key` in local config — the CLI stores defaults (including this key) in a config file on disk under your user account; `treadstone config path` prints the exact path.
4. Saved login session from `treadstone auth login`

If both an API key and a session are present, the **API key wins**.

See [CLI Reference](/docs/cli-reference.md#auth-precedence) for the same rules in one place (useful when wiring automation).

### Human output vs `--json`

Without `--json`, the CLI prints **tables**, short messages, and summaries meant for a terminal. With `--json`, responses are **stable, machine-readable objects** (often mirroring the HTTP API body). Parsers should rely on **`--json` output**, not on the formatting of human mode.

### `--help` at every level

- `treadstone --help` — root groups, global options, and pointers to the built-in quick start.
- `treadstone GROUP --help` — options for that group (if any) and its subcommands.
- `treadstone GROUP SUBCOMMAND --help` — flags, argument names, env vars, and examples for that command.

Use this when you are unsure of a flag name, env var, or the exact argument order.

### `skills` (agent-focused)

The hosted control plane does **not** depend on `skills`. It exists so **AI agents** can learn Treadstone **through the CLI itself**, instead of relying on a separate documentation bundle.

**Why it matters:** the built-in skill teaches an agent *how to think about* Treadstone (when to use `--json`, how auth and sandboxes fit together, where to look next). Combined with **`treadstone --help`** and per-command **`--help`**, the agent can discover flags, env vars, and examples the same way a human would. In practice you can give an agent **only** the `treadstone` binary (or install path): it does not need a dump of the whole docs site, and a human operator does not have to pre-read every page — the agent can self-serve from **help** and **skills** as it works.

**Commands:**

- **`treadstone skills`** (no subcommand) — prints the **built-in agent skill** (`SKILL.md` content) to stdout so you can inspect it or pipe it elsewhere.
- **`treadstone skills install`** — writes that skill to disk as `SKILL.md` under a skills directory. Use **`--target`** to pick a preset (`agents` → `~/.agents/skills`, `cursor`, `codex`, or `project` under the current repo), or **`--dir`** to set a custom base directory (the skill is written to `PATH/treadstone-cli/SKILL.md`).

### Default subcommands

Some **groups** run a default subcommand when you do not pass one:

| Group | If you run | The CLI runs |
|-------|------------|--------------|
| `system` | `treadstone system` | `system health` |
| `sandboxes` | `treadstone sandboxes` | `sandboxes list` (`sb` is an alias for `sandboxes`) |
| `templates` | `treadstone templates` | `templates list` |
| `config` | `treadstone config` | `config get` (interactive behavior may prompt for a key) |
| `skills` | `treadstone skills` | prints the skill (no `install`); see above |

Other groups (`auth`, `api-keys`) require an explicit subcommand — run `treadstone GROUP --help` to see the list.

### Local config

The CLI can store defaults in a **local config file** (`treadstone config path` shows the location). Keys such as `base_url`, `api_key`, and `default_template` reduce repetition; see [CLI Reference](/docs/cli-reference.md#configuration-keys). **Login sessions** are stored separately from this file (they are not managed by `config`).

## Read Next

- [CLI Reference](/docs/cli-reference.md) — full command tables and automation notes
- [API Keys & Auth](/docs/api-keys-auth.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
