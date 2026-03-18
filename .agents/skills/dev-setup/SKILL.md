---
name: dev-setup
description: 首次设置 Treadstone 本地开发环境。克隆仓库后、开始开发前必须完成。涵盖系统依赖安装、Python 环境、Neon 数据库连接配置、迁移、环境验证。只需做一次。当用户/agent 刚进入项目或需要重建环境时使用此 skill。
---

# 本地开发环境设置

这个 skill 只需要执行一次。完成后环境就绪，切换到 `development-lifecycle` skill 开始开发。

## 1. 系统依赖

确认以下工具已安装：

```bash
python3 --version    # 需要 3.12+
uv --version         # Python 包管理器
gh --version         # GitHub CLI（可选，用于 PR/issue 操作）
docker --version     # 容器构建（可选，不影响本地开发）
```

**安装 uv（如果没有）：**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. 安装 Python 依赖

```bash
make install
# 等价于 uv sync，会创建 .venv 并安装所有依赖
```

## 3. 配置数据库（Neon）

项目使用 [Neon](https://neon.tech) Serverless PostgreSQL，无需本地 PostgreSQL。

**获取连接串：**
1. 登录 https://console.neon.tech
2. 找到项目 `treadstone-dev`（或创建一个新项目）
3. 复制连接串，格式为：
   `postgresql://neondb_owner:xxx@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`

**配置 .env：**

```bash
cp .env.example .env
```

编辑 `.env`，将连接串改为 asyncpg 格式：

```bash
# .env
TREADSTONE_DATABASE_URL=postgresql+asyncpg://neondb_owner:xxx@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
TREADSTONE_DEBUG=true
```

注意：URL 中 `postgresql://` 改为 `postgresql+asyncpg://`，保留 `?sslmode=require`。

## 4. 应用数据库迁移

```bash
make migrate
```

Expected 输出：`INFO [alembic.runtime.migration] Context impl PostgresqlImpl.`（有 migration 时会列出具体迁移）

## 5. 验证环境

```bash
make test
```

Expected：全部通过（4 passed 或更多，integration 测试被排除）。

如果测试通过，环境已就绪。

---

## 常见问题

**`uv sync` 失败：**
- 确认 Python 3.12+ 已安装：`python3 --version`
- 尝试：`uv python install 3.12`

**数据库连接失败（`could not connect`）：**
- 检查 `.env` 中的连接串是否正确
- 确认 URL 使用 `postgresql+asyncpg://` 而非 `postgresql://`
- Neon 免费项目会自动挂起，第一次连接可能慢（~1s 冷启动）

**`alembic upgrade head` 报 `authentication failed`：**
- `.env` 未加载：确认 `.env` 文件在项目根目录
- 连接串中密码含特殊字符时需要 URL 编码
