Treadstone
[Treadstone](/)

[Install CLI](/#install)[Docs](/docs)[Pricing](/#pricing)[Sign In](/auth/sign-in)

Agent-native sandbox infrastructure

# Sandboxes for agents  
that don't wait for humans.

Isolated sandboxes for coding, browsing,  
testing, and long-running tasks.

Built so agents can use Treadstone directly—  
launching and managing sandboxes on their own.

[Get Started Free](/auth/sign-up)

bash — treadstone getting started

\> request: check the target page (https://treadstone-ai.dev/) and see what’s going on

thinking: install the treadstone-cli skill for control-plane actions

$ treadstone skills install --target project

✓ installed: .agents/skills/treadstone-cli/SKILL.md

thinking: this task needs a real browser and isolated runtime

thinking: confirm identity

$ treadstone auth whoami

✓ logged in as agent@example.com

thinking: create a sandbox

$ treadstone --json sandboxes create --name page-check

{"id":"sb\_3kx9m2p","status":"running","urls":{"proxy":"https://sb\_3kx9m2p.proxy.treadstone-ai.dev"}}

thinking: prepare a browser session in case human review is needed

$ treadstone --json sandboxes web enable sb\_3kx9m2p

{"open\_link":"https://sb\_3kx9m2p.web.treadstone-ai.dev?token=...","expires\_at":"2026-03-30T18:00:00Z"}

thinking: handoff is ready, stop the runtime

$ treadstone sandboxes stop sb\_3kx9m2p

✓ sandbox stopped

✓ browser session ready for review

awaiting next instruction

// execution model

## Built for autonomous agent workflows.

Agents can create sandboxes, run code, use browsers and tools, and hand work off to humans when needed—through the same control plane.

01 — ORCHESTRATE

Agents control the workflow

Plan tasks, call Treadstone directly, and decide when to create, reuse, or stop a sandbox.

02 — PROVISION

Spin up a real environment

Each sandbox gives agents isolated runtime, files, tools, and browser access—not just a stateless function call.

03 — EXECUTE

Run code, browse, and use tools

Agents work inside the sandbox directly: write code, open pages, inspect files, and keep long-running tasks moving.

04 — HAND OFF

Bring in a human only when needed

Generate a secure browser session when an agent needs review, input, or a final decision.

// integrate

## Three ways in.

CLI for exploration, Python SDK for automation, REST API for integration. All returning the same consistent JSON.

Install cli: curl -fsSL https://treadstone-ai.dev/install.sh | sh

\# 1. Authenticate (or set TREADSTONE\_API\_KEY in env)

$ treadstone auth login --email agent@example.com --password ••••••••

✓ Logged in as agent@example.com

\# 2. Install the agent skill (Cursor, Codex, …)

$ treadstone skills install

Installed: ~/.agents/skills/treadstone-cli/SKILL.md

\# 3. See available templates

$ treadstone --json templates list

{"items": \[{"name": "aio-sandbox-tiny", "cpu": "0.25", "memory": "512Mi"}, ...\]}

\# 4. Create a sandbox — read the ID from JSON output

$ treadstone --json sandboxes create --name agent-demo

{"id": "sb\_3kx9m2p", "status": "running", "urls": {"proxy": "https://sb\_3kx9m2p.proxy.treadstone-ai.dev"}}

\# 5. Hand the browser off to a human

$ treadstone --json sandboxes web enable sb\_3kx9m2p

{"open\_link": "https://sb\_3kx9m2p.web.treadstone-ai.dev?token=...", "expires\_at": "2026-03-30T18:00:00Z"}

// install

## Up in seconds.

Install the CLI on any platform. The SDK and REST API need nothing beyond an API key.

macOS / Linuxcurl installer

`curl -fsSL https://treadstone-ai.dev/install.sh | sh`

WindowsPowerShell

`irm https://treadstone-ai.dev/install.ps1 | iex`

pipPython package

`pip install treadstone-cli`

[GitHub →](https://github.com/earayu/treadstone)[Discord →](https://discord.gg/ygSP9tT5RB)[X →](https://x.com/treadstone_ai)[Releases →](https://github.com/earayu/treadstone/releases)[PyPI →](https://pypi.org/project/treadstone-cli/)

Also available: [pip install treadstone-sdk](https://pypi.org/project/treadstone-cli/)

// pricing

## Start free.  
Scale when you need to.

All plans include the CLI, Python SDK, and REST API. Compute is measured in CU-hours.

Free

ALWAYS FREE

$0

/month

---

- ·10 CU-h compute / month
- ·1 concurrent sandbox
- ·aio-sandbox-tiny (0.25 core, 1 GiB)
- ·2 hr max auto-stop interval
- ·Sandbox lifecycle via CLI, SDK & API
- ·Browser hand-off sessions
- ·Community support

[Get Started Free](/auth/sign-up)

Pro

COMING SOON

Usage-based

pay per CU-hour used

---

- ·80 CU-h compute / month
- ·3 concurrent sandboxes
- ·All templates up to aio-sandbox-medium
- ·10 GiB persistent storage
- ·8 hr max auto-stop interval
- ·Usage analytics & reporting
- ·Priority support

Ultra

COMING SOON

Usage-based

pay per CU-hour used

---

- ·240 CU-h compute / month
- ·5 concurrent sandboxes
- ·All templates up to aio-sandbox-medium
- ·30 GiB persistent storage
- ·24 hr max auto-stop interval
- ·Dedicated SLA & integrations

Custom

ENTERPRISE

Custom

pay per CU-hour used

---

- ·800 CU-h compute / month
- ·10 concurrent sandboxes
- ·100 GiB persistent storage
- ·72 hr max auto-stop interval
- ·12 hr grace period
- ·All sandbox templates
- ·Contact us for terms & SLA

[Contact Us](mailto:support@treadstone-ai.dev)

---

treadstone

Agent-native sandbox platform. Run code, build software, and hand off browser sessions from isolated environments.

RESOURCES
- [Docs Overview](/docs)
- [Install CLI](#install)
- [CLI Guide](/docs?page=cli-guide)
- [REST API Guide](/docs?page=rest-api-guide)
- [Python SDK Guide](/docs?page=python-sdk-guide)
- [REST API Reference](/docs?page=api-reference)
- [CLI on PyPI](https://pypi.org/project/treadstone-cli/)
- [GitHub Releases](https://github.com/earayu/treadstone/releases)

COMMUNITY
- [Star on GitHub ★](https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fearayu%2Ftreadstone)
- [Discord](https://discord.gg/ygSP9tT5RB)
- [X (Twitter)](https://x.com/treadstone_ai)

SUPPORT
- [support@treadstone-ai.dev](mailto:support@treadstone-ai.dev)

© 2026 Treadstone. Apache-2.0 License.Agent-native sandbox platform.