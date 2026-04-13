# End-to-end tests (Hurl)

E2E runs against a **deployed** Treadstone API (default Kind: `http://api.localhost`). See [deploy/README.md](../../deploy/README.md) for `make local`, kubectl context, and networking.

## How to run

```bash
kubectl config use-context kind-treadstone
make local                 # Kind + build + deploy (needs .env.local + Neon; see deploy/README.md)
make test-e2e              # all scenarios
make test-e2e FILE=09-data-plane-proxy.hurl
make test-e2e BASE_URL=http://localhost:8000   # port-forward instead of Ingress
```

`scripts/e2e-test.sh` injects shared variables (`base_url`, `unique`, `admin_email`, per-file `email_XX`, etc.).

## Suite map (by concern)

| File | Plane | What it covers |
|------|--------|----------------|
| `01-auth-session.hurl` | — | Register, email verify, login, `GET /v1/auth/user`, logout, re-login, duplicate register 409 |
| `02-auth-apikey.hurl` | Control | API key CRUD + PATCH rename/disable, scope enforcement (cp-only), disabled key 401, deleted key 401 |
| `03-auth-password.hurl` | — | Change password, old password 401, new password login, password reset request/confirm |
| `04-sandbox-crud.hurl` | Control | Templates, create (202), get, list, delete sandbox |
| `05-sandbox-dual-path.hurl` | Control | Invalid template 403; claim vs persist storage |
| `06-sandbox-names-web-link.hurl` | Control | Name conflict, cross-user names, `urls.web` / `web-link`, DELETE web-link revocation |
| `07-metering-usage.hurl` | Control | `/v1/usage*`, non-admin denied admin routes |
| `08-metering-admin.hurl` | Control | Admin tier templates, user plan, compute grants (uses `admin_email`) |
| `09-data-plane-proxy.hurl` | **Data** | Poll until `ready`; proxy without Bearer → 401; `data_plane.mode=none` → 403; shell exec 200 |
| `10-sandbox-lifecycle.hurl` | Control | Stop → `stopped`, start → `ready`, delete |
| `11-sandbox-lifecycle-ephemeral.hurl` | Control | Full ephemeral lifecycle: create→READY→stop→start→delete, invalid template 403, detail fields |
| `12-sandbox-lifecycle-persistent.hurl` | Control | Persistent sandbox with storage grant, snapshot, stop/start, storage-ledger released |
| `13-sandbox-quota-enforcement.hurl` | Control | Concurrent sandbox limit 429, storage quota 402, admin grant unlocks creation |
| `14-metering-usage-extended.hurl` | Control | Extended usage: storage-ledger filters, grants, `admin/stats` 403 |
| `15-data-plane-proxy-extended.hurl` | **Data** | Scope enforcement: cp-only 403, dp-only key can proxy but 403 on control plane |

## Data plane prerequisites

`09-data-plane-proxy.hurl` and `15-data-plane-proxy-extended.hurl` need a **running sandbox runtime** in the cluster (agent-sandbox + sandbox-runtime charts). They poll `GET /v1/sandboxes/{id}` until `status == "ready"`, then call the HTTP proxy. If the workload inside the pod is down or the command times out, you may see `502 sandbox_unreachable` or slow retries—re-run after `kubectl get pods -n treadstone-prod` (or your env namespace) is healthy.

## GitHub Pages (K8s E2E on `main`)

The **K8s E2E** workflow merges each successful HTML report into the **`gh-pages`** branch: one **batch** per workflow run (`e2e/batches/<run_id>-<run_attempt>/`), a dashboard at **`/e2e/`**, and a small root **`/`** index. In the repo **Settings → Pages**, choose **Deploy from branch** → **`gh-pages`** → **`/`** (not "GitHub Actions" as the source, unless you use a different host).

## Conventions

- **Self-contained files**: each registers its own users (except `08` which relies on `admin_email` from the runner).
- **Email verification**: several flows use `GET /v1/admin/verification-token-by-email` as admin (first user is admin on fresh DB).
- **Retries**: Hurl `[Options] retry` + `retry-interval` poll async state (`ready`, `stopped`).
- **Sandbox template**: `scripts/e2e-test.sh` sets `sandbox_template` (default `aio-sandbox-tiny`) to match the seeded free-tier `allowed_templates`. Do not use `GET /v1/sandbox-templates` `items[0]` — sort order may pick a template the free tier is not allowed to use (→ HTTP 403 `template_not_allowed`).
- **Persist + storage**: free tier seeds `storage_capacity_gib` = 0. Tests needing `persist=true` use admin `POST /v1/admin/users/{id}/storage-grants` first (otherwise HTTP 402 `storage_quota_exceeded`).
- **Web link after sandbox delete**: `GET /v1/sandboxes/{id}/web-link` may return **404** `sandbox_not_found` once the row is gone (fast reconcile); it is not always **200** with `enabled: false`.
- **Inline emails**: files 05, 06, 11–15 use inline emails (`e2e-NN-{{unique}}@test.treadstone.dev`) instead of variables to avoid collisions with parallel-running files.

## Negative tests (data plane)

- No `Authorization` on `/v1/sandboxes/{id}/proxy/...` → `401` (session cookie is not sufficient for the data plane).
- API key with `data_plane.mode=none` → `403` on proxy.
- API key with `control_plane=false` → `403` on control plane endpoints, but `200` on proxy.
