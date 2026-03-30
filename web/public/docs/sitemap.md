# Treadstone Documentation Sitemap

> Complete index of Treadstone documentation. Each link points directly to a Markdown file.
> AI agents: fetch any of these URLs with `Accept: text/markdown` or append `.md` to get raw Markdown.

## Getting Started

- [Overview & Quickstart](/docs/getting-started.md): Why Treadstone, install CLI, create first sandbox, human and agent workflows, template sizes
  - Install CLI (macOS/Linux/Windows/pip)
  - Human workflow quickstart
  - Agent workflow quickstart
  - Built-in sandbox templates table
  - Architecture overview

## Reference

- [CLI Reference](/docs/cli-reference.md): Full command reference for the `treadstone` CLI
  - Configuration (env vars, config file, flags)
  - `system` — health check
  - `auth` — register, login, logout, whoami
  - `sandboxes` — create, list, get, start, stop, delete, web enable/disable
  - `templates` — list available templates
  - `api-keys` — create, list, update, delete
  - `config` — manage local settings
  - JSON output mode (`--json`)
  - AI agent tips

- [SDK Reference](/docs/sdk-reference.md): Python SDK (`treadstone-sdk`) usage
  - Installation
  - Authenticated vs. unauthenticated client
  - sync / asyncio / detailed functions
  - Async usage with `async with`
  - TLS / certificate configuration
  - Module naming convention
  - Agent usage pattern

- [API Reference](/docs/api-reference.md): REST API endpoints
  - Authentication (Bearer token)
  - Base URLs
  - Health, Auth, API Keys, Templates, Sandboxes, Browser Hand-off endpoints
  - Error envelope format
  - Rate limiting
  - Pagination (cursor-based)
  - OpenAPI spec export

## Deployment

- [Self-Hosting](/docs/self-hosting.md): Deploy Treadstone on Kubernetes
  - Prerequisites
  - Helm chart architecture (5 layers)
  - Environment configuration (`.env.local`)
  - OAuth setup
  - One-command local deployment with Kind (`make up`)
  - Step-by-step manual deployment
  - Production deployment
  - Local dev server without Kubernetes
  - Database migrations
  - Make command reference

## Resources

- [GitHub](https://github.com/earayu/treadstone)
- [PyPI: treadstone-cli](https://pypi.org/project/treadstone-cli/)
- [PyPI: treadstone-sdk](https://pypi.org/project/treadstone-sdk/)
- [Releases](https://github.com/earayu/treadstone/releases)
