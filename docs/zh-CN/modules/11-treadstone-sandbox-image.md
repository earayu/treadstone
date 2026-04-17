# Treadstone Sandbox Image：架构与实施说明

> 作者: @Agent-Infra-Sandbox-专家 | 日期: 2026-04-17
> 背景: 在主仓库内落地 Treadstone 自建 sandbox image 第一版，并补齐构建/发布流程

---

## 1. 目标与范围

第一版 `treadstone-sandbox` image 的目标很收敛：

1. 以 `ghcr.io/agent-infra/sandbox:1.0.0.152` 为固定 base image。
2. 不修改 base image 对外暴露的 HTTP / WebSocket / MCP / VNC 等接口行为。
3. 仅在镜像层新增常用 coding agent CLI，供进入 sandbox 的 agent 直接使用。
4. 在主仓库内建立独立的 sandbox image 构建与发布流水线，推送到 GHCR。

**本版明确不做：**

- 不新增 nginx 路由
- 不新增或改造 mcp-hub 配置
- 不通过控制面暴露这些 CLI
- 不改动 sandbox runtime 的服务编排、端口、认证模型

这意味着第一版是一个“保守加层”的镜像方案：保留 upstream sandbox 的运行语义，只扩展工具链。

---

## 2. 架构决策

### 2.1 为什么直接 `FROM agent-infra/sandbox`

`agent-infra/sandbox:1.0.0.152` 已经提供了 Treadstone 需要的完整运行底座：

- nginx 统一入口
- python-server / gem-server / mcp-hub
- Chromium / CDP / VNC / code-server / Jupyter
- shell、文件、browser、MCP 等现成能力

第一版不需要重做这些基础设施。直接继承 upstream image 可以把变更面压到最小，也方便后续对比和回滚。

### 2.2 为什么 pin base image 版本

Dockerfile 固定使用：

```dockerfile
FROM ghcr.io/agent-infra/sandbox:1.0.0.152
```

原因：

- 保证构建可复现
- 避免上游 `latest` 漂移带来行为变化
- 后续排查问题时可以清楚区分“上游升级”与“Treadstone 自己加层”

### 2.3 为什么只预装 CLI，不改服务面

当前诉求是让 sandbox 内的 agent 直接可用几个常见 coding agent CLI：

- Claude Code CLI
- Codex CLI
- Kimi CLI
- Cursor Agent CLI

这些工具都属于“容器内用户态工具链”，不要求控制面对它们做统一编排，也不要求对外暴露额外 API。因此最合适的边界是在镜像层预装，而不是把它们接入控制面或 MCP 层。

---

## 3. 仓库内落地文件

第一版只引入两个核心文件：

```text
deploy/sandbox-image/Dockerfile
.github/workflows/sandbox-image.yml
```

含义分别是：

- `deploy/sandbox-image/Dockerfile`: 定义 Treadstone sandbox image 的镜像层
- `.github/workflows/sandbox-image.yml`: 定义构建并推送到 GHCR 的 GitHub Actions 工作流

目录放在 `deploy/sandbox-image/`，是为了避免和现有 Python 包 `treadstone/sandbox/` 混淆。

---

## 4. Dockerfile 设计

### 4.1 CLI 安装策略

#### Claude Code / Codex

这两个 CLI 都通过 npm 官方包安装：

```dockerfile
RUN npm install -g \
    "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    "@openai/codex@${CODEX_VERSION}"
```

特点：

- base image 已内置 Node.js，可直接安装
- 默认使用 `latest`
- 如后续需要 pin 版本，可直接通过 build args 收紧

#### Kimi CLI

Kimi 的官方安装方式是：

```bash
curl -LsSf https://code.kimi.com/install.sh | bash
```

官方脚本内部的关键逻辑是：

```bash
uv tool install --python 3.13 kimi-cli
```

因此其本质是通过 `uv tool` 安装 `kimi` 可执行文件。

**运行时注意（`gem` 用户）**：`kimi`/`kimi-cli` 的 shebang 可能指向 `uv` 管理的 Python，而默认会落在 **`/root/.local/share/uv/...`**。`gem` 无法使用该解释器路径时会报 **`bad interpreter: Permission denied`**。构建阶段需要把 uv 的 python store **镜像到 `/opt/uv`**，并同步修正 `pyvenv.cfg` 与 `python` shim（见 Dockerfile）。

#### Cursor Agent CLI

Cursor 官方安装方式是：

```bash
curl https://cursor.com/install -fsS | bash
```

在之前的实机验证中，这个安装器会把二进制落到 `~/.local/bin/`，并提供 `cursor-agent` 命令。

**运行时注意（`gem` 用户）**：sandbox 里常见交互用户是 `gem`（uid 1000），默认 **无法进入** `/root`（0700）。如果 Cursor 只装在 `/root/.local/bin`，则会出现 **`agent: command not found`**（即使 root 下可用）。因此 Dockerfile 在构建阶段会把安装目录镜像到 **`/opt/cursor-agent/share`**，并在 **`/usr/local/bin`** 放置全局可用的 `agent` / `cursor-agent` 符号链接。

### 4.2 PATH 设计

Dockerfile 里需要尽早设置：

```dockerfile
ENV PATH="/root/.local/bin:${PATH}"
```

这是第一版里一个很关键的实施细节，原因有两个：

1. Cursor Agent 安装后位于 `~/.local/bin`
2. Kimi 官方脚本会先安装 `uv`，再立刻调用 `uv tool install`

如果在运行 Kimi 安装脚本之前没有把 `/root/.local/bin` 放进 PATH，那么脚本在同一个 `RUN` 层内可能找不到刚装好的 `uv`，导致 Docker build 失败。

### 4.3 安装完成后的显式校验

Dockerfile 通过版本命令做即时失败：

```dockerfile
RUN claude --version \
    && codex --version \
    && kimi --version \
    && cursor-agent --version
```

这样做的目的是把安装问题暴露在 build 阶段，而不是留到运行时才发现命令不存在。

### 4.4 已知限制

第一版有两个已知限制，需要在设计上接受：

1. `cursor.com/install` 当前没有稳定的版本化下载 URL，因此 Cursor Agent 实际上总是拉取 upstream latest。
2. Kimi 官方安装脚本同样走官方最新安装路径，没有在 Dockerfile 中做额外版本 pin。

因此：

- **base image 是固定版本**
- **部分预装 CLI 是 latest 策略**

这是一个有意识的折中：先把 image pipeline 和工具链打通，再根据运行稳定性决定是否为这些 CLI 建立更强的版本锁定策略。

---

## 5. GitHub Actions 设计

工作流文件：`.github/workflows/sandbox-image.yml`

### 5.1 触发方式

工作流支持两种触发：

1. 推送 tag：

```yaml
on:
  push:
    tags:
      - "sandbox-v*"
```

2. 手动触发：

```yaml
workflow_dispatch:
  inputs:
    version:
```

约定：

- git tag 用 `sandbox-v0.1.0`
- 最终镜像 tag 用 `v0.1.0`
- `workflow_dispatch` 仅作为“从 `main` 手动发布一个新的 version”的入口，不允许从任意 branch 发布正式版本

工作流里会把 `sandbox-` 前缀剥掉，得到真正的 image version。
如果 `workflow_dispatch` 不是从 `main` 分支触发，workflow 会直接失败，而不是仅仅 checkout `main` 后继续发布。

### 5.2 为什么不用 `paths` filter

GitHub Actions 的 `on.push.paths` 对 tag push 不生效，因此不能依赖它来区分“API image 发布”和“sandbox image 发布”。

所以这里直接采用独立 tag 前缀：

- API / 主服务：继续使用现有版本线
- sandbox image：使用 `sandbox-v*`

这比 `paths` filter 更直接，也更符合 GitHub 的触发语义。

### 5.3 推送目标

镜像推送到：

```text
ghcr.io/<github.repository_owner>/treadstone-sandbox
```

标签策略：

- `${version}`，例如 `v0.1.0`
- `latest`

这保证了：

- 可以按显式版本回滚
- 也能让试验环境直接消费最新镜像

---

## 6. 推荐发布流程

### 6.1 首次发布

1. 合并包含 Dockerfile 和 workflow 的 PR
2. 在主仓库打 tag：

```bash
git tag sandbox-v0.1.0
git push origin sandbox-v0.1.0
```

3. GitHub Actions 自动构建并推送：

```text
ghcr.io/earayu/treadstone-sandbox:v0.1.0
ghcr.io/earayu/treadstone-sandbox:latest
```

### 6.2 手动重建

如果不想重新打 tag，也可以直接在 GitHub Actions 中使用 `workflow_dispatch`，手工输入一个**尚未发布过的新版本号**（例如 `v0.1.1`）从 `main` 触发构建。

工作流会额外做三层保护：

1. `workflow_dispatch` 时固定 checkout `main`
2. 如果触发来源不是 `main` 分支，则直接失败，拒绝从非主干发布正式版本
3. 如果 `ghcr.io/<owner>/treadstone-sandbox:${version}` 已经存在，则直接失败，拒绝重复发布同一个 semver

---

## 7. 本地验证建议

建议至少做两类验证：

### 7.1 构建验证

```bash
docker build \
  -f deploy/sandbox-image/Dockerfile \
  -t treadstone-sandbox:test \
  deploy/sandbox-image
```

### 7.2 工具链验证

容器启动后检查：

```bash
claude --version
codex --version
kimi --version
cursor-agent --version
```

若某个命令缺失，应优先检查：

- 是否仍位于 `/root/.local/bin`
- 安装脚本是否改了默认行为
- upstream base image 是否改了默认用户或 shell 环境

---

## 8. 后续演进方向

第一版完成后，可以按风险从低到高考虑后续增强：

1. 为各 CLI 建立更强的版本 pin 策略
2. 给 sandbox runtime chart 增加 image tag 的独立发布切换流程
3. 增加针对 sandbox image 的 smoke test job
4. 评估是否需要把部分 agent tooling 与 Treadstone CLI / 控制面能力做更深集成

这些都应在“保持 base image 对外行为稳定”的前提下逐步推进，而不是在第一版里一次性引入。
