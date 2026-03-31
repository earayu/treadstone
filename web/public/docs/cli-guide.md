# CLI Guide

## What this page is for

Use this page when you install the CLI, wire **automation** (`--json`, env vars), or need to know how **credentials** and **defaults** behave. Command-by-command tables live in [CLI Reference](/docs/cli-reference.md); workflow-oriented steps are in [Quickstart](/docs/quickstart.md), [Sandbox Lifecycle](/docs/sandbox-lifecycle.md), and [API Keys & Auth](/docs/api-keys-auth.md).

The `treadstone` binary talks to the **control plane** only. Sandbox workloads, auth, API keys, and browser handoff are covered in those workflow docs—here we focus on installation, global flags, output modes, `skills`, and groups that run a default subcommand.

## Install

```bash
# macOS / Linux
curl -fsSL https://treadstone-ai.dev/install.sh | sh

# Windows (PowerShell)
irm https://treadstone-ai.dev/install.ps1 | iex

# PyPI (package name treadstone-cli; the binary is still `treadstone`)
pip install treadstone-cli
```

Then:

```bash
treadstone --version
treadstone --help
```

## Command layout

Put **global options before the subcommand**:

```text
treadstone [OPTIONS] <group> <subcommand> [args ...]
```

Example: `treadstone --json --base-url https://api.example.com sandboxes list`

## Core CLI behavior

### Global options (root command)

These flags apply to the whole invocation and are parsed before the subcommand:

| Option | Purpose |
|--------|---------|
| `--json` | Print structured JSON instead of human-oriented tables and sentences. Use when a script, agent, or CI job parses the result. |
| `--api-key` | API key for this run only. Same effect as `TREADSTONE_API_KEY` for that process (see below). |
| `--base-url` | Control-plane base URL (hosted, self-hosted, or local dev). Overrides `TREADSTONE_BASE_URL` when set on the command line. |
| `--version` | Print the CLI version and exit (no API call). |

`--help` is available on the root command and on every group and subcommand; it is omitted from the table because Click adds it automatically.

### Environment variables

These are read when you do not pass the matching flag (flags win over env for the same setting):

| Variable | Used for |
|----------|----------|
| `TREADSTONE_API_KEY` | Default API key (same role as saved `api_key` in config; precedence order below). |
| `TREADSTONE_BASE_URL` | Default API base URL before the value in config or the built-in default. |
| `TREADSTONE_DEFAULT_TEMPLATE` | Default template for `sandboxes create` when `--template` is omitted. Takes precedence over the `default_template` config key. |

### Credential precedence

Commands that need authentication resolve credentials in this order (highest priority first):

1. `--api-key` flag
2. `TREADSTONE_API_KEY` environment variable
3. Saved `api_key` in local config — `treadstone config path` prints the config file; the key is stored in that file.
4. Saved login session from `treadstone auth login` (stored separately from config, under the same config directory)

If both an API key and a session are present, the **API key wins**.

See [CLI Reference — Auth precedence](/docs/cli-reference.md#auth-precedence) for the same rules in compact form.

### Human output vs `--json`

Without `--json`, the CLI prints tables, short messages, and summaries for a terminal. With `--json`, responses are stable, machine-readable objects (often mirroring the HTTP API body). Parsers should rely on `--json` output, not on the formatting of human mode.

### `--help` at every level

- `treadstone --help` — root groups, global options, quick start examples, and active configuration summary.
- `treadstone GROUP --help` — options for that group (if any) and its subcommands.
- `treadstone GROUP SUBCOMMAND --help` — flags, argument names, env vars, and examples for that command.

### Default subcommands

Some **groups** run a default action when you omit the subcommand:

| Group | If you run | The CLI runs |
|-------|------------|--------------|
| `system` | `treadstone system` | `system health` |
| `sandboxes` | `treadstone sandboxes` | `sandboxes list` (`sb` is an alias for `sandboxes`) |
| `templates` | `treadstone templates` | `templates list` |
| `config` | `treadstone config` | `config get` with no key — prints all configured keys (secrets such as `api_key` are masked) |
| `skills` | `treadstone skills` | prints the built-in agent guide to stdout; see [skills](#skills-agent-focused) |

Other groups (`auth`, `api-keys`) require an explicit subcommand — run `treadstone GROUP --help` to see the list.

### `skills` (agent-focused)

The hosted control plane does not depend on `skills`. The command exists so agents can learn Treadstone through the CLI instead of a separate documentation bundle.

The embedded guide explains when to use `--json`, how auth and sandboxes fit together, and where to look next. Together with `treadstone --help` and per-command `--help`, an agent can discover flags, env vars, and examples the same way a human would.

Commands:

- `treadstone skills` — print the built-in agent guide (`SKILL.md` content) to stdout so you can inspect it or pipe it elsewhere.
- `treadstone skills install` — write that content to disk as `SKILL.md` under a skills directory. Use `--target` to pick a preset (`agents` → `~/.agents/skills`, `cursor`, `codex`, or `project` under the current repo), or `--dir` to set a custom base directory (the file is written to `PATH/treadstone-cli/SKILL.md`).

### Local config

The CLI stores defaults in a TOML file; `treadstone config path` prints its path. Valid keys include `base_url`, `api_key`, and `default_template` — see [CLI Reference — Configuration keys](/docs/cli-reference.md#configuration-keys). **Login sessions** are stored in a separate file next to that config and are not managed through `config set` / `config get`.

## Read next

- [CLI Reference](/docs/cli-reference.md) — full command tables and automation notes
- [Quickstart](/docs/quickstart.md)
- [REST API Guide](/docs/rest-api-guide.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
