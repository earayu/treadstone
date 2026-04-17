# `agent-infra/sandbox:1.0.0.152` 重建方案

## 背景

Treadstone 当前已有一条自建 sandbox image 主线：`deploy/sandbox-image/Dockerfile` 在
`ghcr.io/agent-infra/sandbox:1.0.0.152` 之上继续安装 Claude Code、Codex、Kimi、Cursor Agent。

这条文档记录的是另一条实验线：在**不再 `FROM ghcr.io/agent-infra/sandbox`** 的前提下，尽可能把
`agent-infra/sandbox:1.0.0.152` 的运行时行为重建出来，便于后续脱离上游镜像继续演进。

## 已确认事实

- `ghcr.io/agent-infra/sandbox:1.0.0.152` 和
  `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.0.0.152`
  是同一个 digest。
- `agent-infra/sandbox` 公开仓库的 `v1.0.0.152` tag 不包含原始 Dockerfile，也不包含 runtime image history
  里的私有 build context（`config/`、`configs/`、`server/`、`python-server/`、`wheels/` 等）。
- 公开 workflow `.github/workflows/push-to-ghcr.yml` 只是把 Volcengine 上的镜像 mirror 到 GHCR，
  不是公开 repo 直接 build。

结论：

- **无法保证逐字还原上游私有 Dockerfile**
- 但可以基于 image history、live container 和小体积 runtime 资产做出一版**高保真重建**

## 仓库落点

重建方案落在：

- `deploy/sandbox-image/reconstructed/Dockerfile`
- `deploy/sandbox-image/reconstructed/runtime/`
- `.github/workflows/sandbox-image-reconstructed.yml`

这里没有覆盖现有的 `deploy/sandbox-image/Dockerfile`，因为现有文件仍然承担
“在 upstream sandbox 上叠加 Treadstone CLI 层”的生产主线。

## 这版重建做了什么

### 直接复用 runtime 小资产

从已发布镜像提取并入库：

- `/opt/gem`
- `/opt/gem-server`
- `/opt/aio`
- `/opt/terminal`
- `/opt/application`
- `/opt/python3.12/site-packages/app`
- `/opt/python3.12/site-packages/vendors`

这些目录总量较小，但包含了真正的运行链：

- `run.sh`
- `entrypoint.sh`
- `supervisord/*.conf`
- `nginx/*.conf`
- `python-server` 的 `app.cli:cli`
- `gem-server` 源码树

### 用公开 URL 重建大件运行时

Dockerfile 不把大体积二进制直接入库，而是在 build 时下载：

- Python 3.11 / 3.12 standalone tarball
- Chromium 133 for Testing（当前仅 `linux/amd64`）
- code-server `4.104.0`
- noVNC `v1.4.0`
- websocat `v1.13.0`
- Node 22 + npm globals：
  - `@agent-infra/mcp-hub@1.1.0`
  - `@agent-infra/mcp-server-browser@1.2.21`
  - `chrome-devtools-mcp@0.9.0`

### Python 运行时

`python-server` 没有公开源码仓库可直接引用，因此采用：

1. 从镜像提取 `app/` 与 `vendors/`
2. 基于 wheel metadata 整理最小运行时依赖
3. 直接在镜像里写出 `/usr/local/bin/python-server` entry script

`gem-server` 则可直接从提取出的 `/opt/gem-server` 源码树做本地安装。

## 当前边界

### 能保证的

- build context 不再 `FROM ghcr.io/agent-infra/sandbox`
- 主入口、healthcheck、supervisord/nginx/python-server/gem-server 的运行链可追溯
- 可以用独立 workflow 构建并推送到 GHCR

### 不能保证的

- 无法声明为“上游私有 Dockerfile 的逐字还原”
- 当前只验证 `linux/amd64`
- Chromium / code-server / Node / Python 依赖链仍依赖外部下载源

## 本地构建

```bash
export https_proxy=http://127.0.0.1:8118
export http_proxy=http://127.0.0.1:8118

docker buildx build \
  --load \
  --platform linux/amd64 \
  -f deploy/sandbox-image/reconstructed/Dockerfile \
  -t treadstone-sandbox-reconstructed:test \
  deploy/sandbox-image/reconstructed
```

如果本地构建失败，允许保留失败点并在 PR 中说明，不阻塞这一轮“先把重建骨架入库”的目标。

## 发布工作流

`.github/workflows/sandbox-image-reconstructed.yml` 的约束与现有 image pipeline 保持一致：

- tag 前缀：`sandbox-reconstructed-v*`
- 目标镜像：`ghcr.io/<owner>/treadstone-sandbox-reconstructed`
- `workflow_dispatch` 只能从 `main` 发正式版本
- 已存在的 semver 不允许重复发布

## 建议的后续验证

1. 先在本地完成一轮 `docker buildx build --platform linux/amd64`
2. 基于 PR 让 GitHub Actions 真机跑一轮 reconstructed image workflow
3. 如 build 成功，再逐步补 runtime 对照：
   - `/opt` 树 diff
   - 容器 env diff
   - 端口与健康检查
   - `http://localhost:8080`、`/v1/docs`、browser/CDP、Jupyter、code-server
