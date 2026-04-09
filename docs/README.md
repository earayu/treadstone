# Documentation

Contributor-facing design notes and audits for the Treadstone repository.

## Chinese (中文)

Contributor-facing Chinese docs live under **`docs/zh-CN/`** (this directory; use lowercase `docs` in paths).

- **Index:** [docs/zh-CN/README.md](zh-CN/README.md) — module map and how to maintain these docs.
- **Server logging audit:** [docs/zh-CN/modules/08-logging-audit.md](zh-CN/modules/08-logging-audit.md) — log placement, levels (Debug/Info/Warning/Error), duplication risks, call inventory, and follow-up recommendations.
- **Cold snapshot / restore design:** [docs/zh-CN/modules/09-cold-snapshot-restore.md](zh-CN/modules/09-cold-snapshot-restore.md) — persistent sandbox cold storage, restore orchestration, and current ACK-first boundaries.

Public, user-facing documentation for the product lives under `web/public/docs/` and is maintained per [`treadstone-public-docs`](../.agents/skills/treadstone-public-docs/SKILL.md) skill.
