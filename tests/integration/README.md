# 集成测试

集成测试跑在真实的 Neon PostgreSQL 上，验证完整的数据库交互流程。

## 前置条件

1. 在 Neon Console 中为项目创建一个 **test 分支**（不要用主分支）
2. 复制 `.env.test.example` 为 `.env.test` 并填入 test 分支的连接串：

```bash
cp tests/integration/.env.test.example tests/integration/.env.test
# 编辑 .env.test，填入你的 Neon test 分支连接串
```

3. 确保 Alembic 迁移已在 test 分支上执行：

```bash
# 临时指向 test 分支（或直接在 Neon Console fork 已有迁移的主分支）
make migrate
```

> **注意：** `.env.test` 包含数据库密码，已被 `.gitignore` 排除，绝不会被提交。

## 运行

```bash
make test-all          # 运行全部测试（含集成测试）
```

或单独运行集成测试：

```bash
uv run pytest tests/integration/ -v -m integration
```

## 工作原理

- `conftest.py` 在每个测试函数执行前读取 `.env.test` 中的 `TREADSTONE_DATABASE_URL`
- 用该 URL 重建 SQLAlchemy async engine，替换全局 engine
- 如果 `.env.test` 不存在，回退到项目根目录 `.env` 中的默认连接串
- 每个测试结束后自动清理创建的测试数据（带唯一 token 前缀）

## 测试清单

| 测试 | 验证内容 |
|------|---------|
| `test_tables_exist` | Alembic 迁移正确创建了 user/oauth_account/invitation/api_key 表 |
| `test_register_creates_user_in_db` | 注册 API 在真实 DB 中创建了用户记录 |
| `test_full_auth_flow` | 完整流程：注册 → 登录 → 获取用户 → 修改密码 → 新密码登录 |
| `test_duplicate_register_returns_400` | 重复邮箱注册返回 400 |
| `test_config_endpoint_returns_auth_info` | `/api/config` 返回正确的认证配置 |
| `test_neon_connection_and_version` | 基础连接验证（位于 `test_db.py`） |

## 为什么用 Neon test 分支？

- **隔离性**：测试数据不会污染生产/开发分支
- **一致性**：test 分支从主分支 fork，schema 保持同步
- **可重置**：随时可在 Neon Console 中 reset test 分支到主分支状态
- **零成本**：Neon 分支是 copy-on-write，不占额外存储
