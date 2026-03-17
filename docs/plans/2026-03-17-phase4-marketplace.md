# Phase 4：Sandbox Template + Skill Pack 市场 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让开发者发布 Sandbox Template 和 Skill Pack，用户自由组合为垂直 Agent，形成 Marketplace。

**Architecture:** Template 和 Skill 以声明式 YAML 存储在 DB 中，组合引擎将 Template + Skills 合成为最终的 SandboxClaim 配置。Marketplace API 提供发布、搜索、评分能力。

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2

---

### Task 1：Template 和 Skill 数据模型

**Files:**
- Create: `treadstone/models/template.py`
- Create: `treadstone/models/skill.py`
- Alembic migration

**要点：**

`SandboxTemplate` 表（平台层，不同于 K8s CRD 层的 SandboxTemplate）：
- id, name, description, author_id
- spec (JSONB) — 包含 base_image, resources, env_vars, ports 等
- category, tags
- version, published_at
- downloads_count, rating_avg

`SkillPack` 表：
- id, name, description, author_id
- spec (JSONB) — 包含 MCP server 定义、tools 列表、prompt 模板
- category, tags
- version, published_at
- downloads_count, rating_avg

**Commit:** `feat: template and skill data models`

---

### Task 2：Template / Skill CRUD API

**Files:**
- Create: `treadstone/api/template.py`
- Create: `treadstone/api/skill.py`
- Create: `treadstone/services/template_service.py`
- Create: `treadstone/services/skill_service.py`

**要点：**
- 标准 CRUD：创建、查询、列表（分页+搜索）、更新、删除
- 发布/下架状态管理
- 版本管理（简单的版本号递增）
- 只有作者可以修改/删除自己的 template/skill

**Commit:** `feat: template and skill CRUD APIs`

---

### Task 3：组合引擎

**Files:**
- Create: `treadstone/services/compose_engine.py`
- Test: `tests/test_compose_engine.py`

**要点：**

核心函数 `compose(template_id, skill_ids) -> SandboxClaimSpec`：
1. 读取 template 的 spec（base image, resources）
2. 读取每个 skill 的 spec（MCP servers, tools, env vars）
3. 合并为一个完整的 SandboxClaim 配置：
   - 容器 image = template 定义的 base image
   - 环境变量 = template env + skills env 合并
   - MCP servers = 所有 skills 的 MCP server 列表
   - 资源 = template 定义的 resources
4. 返回可直接提交给 k8s_client 的配置

**Commit:** `feat: compose engine (template + skills → sandbox config)`

---

### Task 4：Marketplace API

**Files:**
- Create: `treadstone/api/marketplace.py`
- Create: `treadstone/services/marketplace_service.py`

**要点：**
- `GET /api/marketplace/templates` — 搜索 templates（按 category, tags, rating 排序）
- `GET /api/marketplace/skills` — 搜索 skills
- `POST /api/marketplace/compose` — 组合 template + skills，创建沙箱
- `POST /api/marketplace/rate/{item_id}` — 评分

组合创建的流程：
```
POST /api/marketplace/compose
  body: { template_id: "xxx", skill_ids: ["a", "b"] }
    → compose_engine.compose(template_id, skill_ids) → sandbox_config
    → sandbox_service.create(config=sandbox_config) → sandbox
    → 返回 sandbox info
```

**Commit:** `feat: marketplace API with compose and search`
