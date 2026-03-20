# 部署与端到端测试指南

本文档介绍如何将 Treadstone 部署到 Kind 本地 K8s 集群，并进行端到端（E2E）测试。

## 前置条件

- Docker Desktop 已安装并运行
- Kind 已安装（`brew install kind`）
- kubectl 已安装（`brew install kubectl`）
- Helm 已安装（`brew install helm`）
- Treadstone Kind 集群已创建（参见 `deploy/kind/kind-config.yaml`）
- agent-sandbox controller 已部署（CRDs + controller Pod）
- Neon 数据库已配置（`.env` 中有 `TREADSTONE_DATABASE_URL`）

## Step 1：构建 Docker 镜像

```bash
cd /path/to/treadstone
docker build -t treadstone:dev .
kind load docker-image treadstone:dev --name treadstone
```

## Step 2：部署 SandboxTemplate

SandboxTemplate 定义了 Sandbox Pod 的镜像和资源配置，由 Helm chart 管理：

```bash
helm upgrade --install sandbox-runtime deploy/sandbox-runtime -n treadstone
```

验证：

```bash
kubectl -n treadstone get sandboxtemplates
# 应输出：
# NAME                 AGE
# treadstone-sandbox   ...
```

## Step 3：创建 K8s Secret

Treadstone 需要数据库连接串、JWT Secret 等敏感配置。从 `.env` 文件创建 Secret：

```bash
kubectl -n treadstone create secret generic treadstone-secrets --from-env-file=.env
```

> **注意**：`.env` 中的 `TREADSTONE_DEBUG` 必须是 `false`，否则会使用 FakeK8sClient 而非真实 K8s API。如果你的 `.env` 中是 `true`，需要手动修改 Secret：
>
> ```bash
> kubectl -n treadstone get secret treadstone-secrets -o json | \
>   python3 -c "import sys,json,base64; s=json.load(sys.stdin); s['data']['TREADSTONE_DEBUG']=base64.b64encode(b'false').decode(); json.dump(s,sys.stdout)" | \
>   kubectl apply -f -
> ```

## Step 4：部署 Treadstone

```bash
helm upgrade --install treadstone deploy/treadstone -n treadstone \
  --set image.repository=treadstone \
  --set image.tag=dev \
  --set image.pullPolicy=Never \
  --set env.TREADSTONE_DEBUG=false \
  --set env.TREADSTONE_SANDBOX_NAMESPACE=treadstone \
  --set envSecretRef=treadstone-secrets
```

等待 Pod Ready：

```bash
kubectl -n treadstone rollout status deploy/treadstone-treadstone --timeout=60s
```

## Step 5：运行数据库迁移

首次部署或代码有新 migration 时需要执行：

```bash
kubectl -n treadstone exec deploy/treadstone-treadstone -- uv run alembic upgrade head
```

## Step 6：访问服务

Kind 集群已自动安装 ingress-nginx 并配置了端口映射（80/443），Helm chart 默认创建 Ingress 资源。部署完成后可直接通过 `http://localhost` 访问：

```bash
curl -s http://localhost/health
```

> **备选方案**：如果 Ingress 不可用（端口冲突、未安装 ingress-nginx 等），可以用 port-forward：
>
> ```bash
> make port-forward
> # 然后通过 http://localhost:8000 访问
> ```

在新终端中继续以下步骤。

---

## E2E 测试

> **注意**：以下示例使用 `http://localhost`（通过 Ingress）。如果你使用 port-forward，请将 URL 替换为 `http://localhost:8000`。

### 6.1 健康检查

```bash
curl -s http://localhost/health
```

期望输出：

```json
{"status":"ok"}
```

### 6.2 注册用户

第一个注册的用户自动成为 admin：

```bash
curl -s -X POST http://localhost/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"StrongPass123!"}' | python3 -m json.tool
```

期望输出：

```json
{
    "id": "user...",
    "email": "admin@example.com",
    "role": "admin"
}
```

### 6.3 登录并创建 API Key

```bash
# 登录（Cookie-based，返回 204 + Set-Cookie）
curl -s -c /tmp/cookies -X POST http://localhost/v1/auth/login \
  -d "username=admin@example.com&password=StrongPass123!"

# 创建 API Key
curl -s -b /tmp/cookies -X POST http://localhost/v1/auth/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name":"e2e-test"}' | python3 -m json.tool
```

记下返回的 `key` 值（`sk-...`），后续使用：

```bash
export API_KEY="sk-your-key-here"
```

### 6.4 查看 Sandbox 模板

```bash
curl -s http://localhost/v1/sandbox-templates \
  -H "Authorization: Bearer $API_KEY" | python3 -m json.tool
```

期望输出中包含通过 Helm 部署的 `treadstone-sandbox` 模板（而非 `python-dev` / `nodejs-dev` — 那是 FakeK8sClient 的默认数据，说明 debug 没关）。

### 6.5 创建 Sandbox

```bash
curl -s -X POST http://localhost/v1/sandboxes \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"treadstone-sandbox","name":"e2e-test-sb"}' | python3 -m json.tool
```

期望：HTTP 202，`status: "creating"`。

验证 K8s 资源已创建：

```bash
kubectl -n treadstone get sandboxclaims
kubectl -n treadstone get sandboxes
kubectl -n treadstone get pods
```

应看到名为 `e2e-test-sb` 的 SandboxClaim、Sandbox 和 Pod。

> **注意**：在 Kind 集群中 Pod 可能处于 `CrashLoopBackOff`，因为 Kind 无法直接拉取 `ghcr.io/agent-infra/sandbox:latest` 镜像。这是环境限制，不影响 API 层面的验证。如需 Pod 正常运行，需要先手动拉取镜像并 `kind load` 到集群中。

### 6.6 查看 Sandbox 详情

```bash
# 用上一步返回的 sandbox id
curl -s http://localhost/v1/sandboxes/{sandbox_id} \
  -H "Authorization: Bearer $API_KEY" | python3 -m json.tool
```

### 6.7 列出所有 Sandbox

```bash
curl -s http://localhost/v1/sandboxes \
  -H "Authorization: Bearer $API_KEY" | python3 -m json.tool
```

### 6.8 删除 Sandbox

```bash
curl -s -X DELETE http://localhost/v1/sandboxes/{sandbox_id} \
  -H "Authorization: Bearer $API_KEY" -w "\nHTTP Status: %{http_code}\n"
```

期望：HTTP 204。验证 K8s 资源已删除：

```bash
kubectl -n treadstone get sandboxclaims
# e2e-test-sb 应已消失
```

---

## 重新部署（代码变更后）

```bash
docker build -t treadstone:dev .
kind load docker-image treadstone:dev --name treadstone
kubectl -n treadstone rollout restart deploy/treadstone-treadstone
kubectl -n treadstone rollout status deploy/treadstone-treadstone --timeout=60s
```

如有新 migration：

```bash
kubectl -n treadstone exec deploy/treadstone-treadstone -- uv run alembic upgrade head
```

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| Templates API 返回 `python-dev` / `nodejs-dev` | `TREADSTONE_DEBUG=true`，使用了 FakeK8sClient | 确保 Secret 中 `TREADSTONE_DEBUG=false` |
| API 返回 500 + `column "xxx" does not exist` | 数据库缺少新列 | 执行 `alembic upgrade head` |
| Create Sandbox 返回 202 但 K8s 无资源 | K8s API 调用静默失败 | 查看 Pod 日志 `kubectl logs deploy/treadstone-treadstone` |
| Pod 一直不 Ready | 镜像拉取失败 | `kind load docker-image` 加载镜像到集群 |
| 403 Forbidden in pod logs | RBAC 权限不足 | 确认 Helm chart 部署了 ClusterRole + ClusterRoleBinding |
| `curl localhost` 连接被拒绝 | ingress-nginx 未安装或 Kind 缺少端口映射 | 重建集群 `make kind-delete && make kind-create`，或用 `make port-forward` 代替 |
