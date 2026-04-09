# 模块 9：Persistent Sandbox 冷存快照与恢复

## 模块目标

这个模块描述 `persist=true` 的 direct sandbox 如何在 **保留工作区数据** 的前提下释放 live disk，把状态切到 `cold`，并在 `restore` 或 `start` 时重新 materialize 出 PVC/PV。

当前实现主要落在：

- `treadstone/models/sandbox.py`
- `treadstone/models/metering.py`
- `treadstone/services/sandbox_service.py`
- `treadstone/services/storage_snapshot_orchestrator.py`
- `treadstone/services/k8s_client.py`
- `treadstone/services/k8s_sync.py`
- `treadstone/api/sandboxes.py`
- `deploy/cluster-storage/templates/volumesnapshotclass.yaml`

## 1. 产品模型

这一版实现采用的是 **sandbox 绑定式 cold snapshot**，而不是独立 snapshot 资源模型。

对用户来说，公开对象仍然只有 `sandbox`：

- 用户不会单独管理 snapshot 列表
- 每个 persistent direct sandbox 在任意时刻最多只绑定一份 cold snapshot
- `snapshot` 的含义固定为：
  - 若当前 `ready`，先停机
  - 对 workspace PVC 做快照
  - 显式删除 Sandbox CR 和 workspace PVC
  - sandbox 进入 `cold`
- `restore` 的含义固定为：
  - 从绑定 snapshot 恢复 live disk
  - 恢复完成后 sandbox 回到 `stopped`
- `start` 对 `cold` sandbox 会自动触发 restore，然后再启动到 `ready`

这让用户只需要理解一件事：

- `stopped` 代表磁盘还挂着，恢复快
- `cold` 代表磁盘已经释放，恢复更慢但更省钱、调度更灵活

## 2. 当前公开状态与字段

### 主状态

当前 `Sandbox.status` 包括：

- `creating`
- `ready`
- `stopped`
- `cold`
- `error`
- `deleting`

其中 `cold` 是这次新增的稳定状态，表示：

- 没有 live PVC / PV / disk
- 仍然保留一份可恢复的 cold snapshot
- 继续占用 storage quota，但不占用 compute

### 异步操作覆盖层

为了避免把“后台正在做 snapshot / restore”混进主状态机，这次实现新增了 `pending_operation`：

- `snapshotting`
- `restoring`

它是对主状态的覆盖层，不是新的生命周期终态。

当前实现里还有一个内部辅助字段：

- `pending_operation_target_status`

它只用于恢复路径区分两种目标：

- `restore only` -> 目标是 `stopped`
- `start on cold` -> 目标是 `ready`

### 新增存储元数据

当前 `Sandbox` 行会额外记录：

- `storage_backend_mode`
- `k8s_workspace_pvc_name`
- `k8s_workspace_pv_name`
- `workspace_volume_handle`
- `workspace_zone`
- `snapshot_provider_id`
- `snapshot_k8s_volume_snapshot_name`
- `snapshot_k8s_volume_snapshot_content_name`
- `gmt_snapshotted`
- `gmt_restored`
- `gmt_snapshot_archived`（仅预留，v1 未启用）

API 返回里新增：

- `pending_operation`
- `storage.mode`
- `storage.size`
- `storage.snapshot_created_at`
- `storage.zone`

## 3. 当前公开接口

在原有 sandbox CRUD 之上，这次新增两个接口：

- `POST /v1/sandboxes/{sandbox_id}/snapshot`
- `POST /v1/sandboxes/{sandbox_id}/restore`

并扩展了：

- `POST /v1/sandboxes/{sandbox_id}/start`

当前语义如下：

### `POST /snapshot`

只支持：

- `persist=true`
- `provision_mode="direct"`

状态约束：

- `ready`：先走 stop，再进入 `snapshotting`
- `stopped`：直接进入 `snapshotting`
- `cold` / `deleting` / `creating` / 已有 `pending_operation`：返回 `409`

### `POST /restore`

只支持：

- `status="cold"`
- `storage_backend_mode="standard_snapshot"`

效果：

- sandbox 保持 `cold`
- `pending_operation="restoring"`
- 后台恢复完成后回到 `stopped`

### `POST /start`

当前有两条路径：

- `stopped|error`：沿用原来的 scale-up
- `cold`：改为 `restore_on_start`

即：

- 先进入 `pending_operation="restoring"`
- 后台从 snapshot 恢复 PVC/PV
- 恢复成功后直达 `ready`

## 4. Kubernetes 与 ACK 实现方式

这次实现的产品模型是云无关的，但 v1 provider 是 ACK-first。

### 通用 K8s 能力

真正依赖的 Kubernetes 通用接口包括：

- `VolumeSnapshotClass`
- `VolumeSnapshot`
- `VolumeSnapshotContent`
- `PersistentVolumeClaim.spec.dataSource`
- `WaitForFirstConsumer`

### ACK-first 的具体落地

当前默认 snapshot class 配置是：

- `TREADSTONE_SANDBOX_VOLUME_SNAPSHOT_CLASS=treadstone-workspace-snapshot`

Helm 增加了：

- `deploy/cluster-storage/templates/volumesnapshotclass.yaml`

RBAC 新增权限：

- `volumesnapshots`
- `volumesnapshotcontents`
- `volumesnapshotclasses`
- `persistentvolumeclaims`
- `persistentvolumes`

这一版还没有直接调用 ECS API 做 snapshot import/export；v1 的 cold asset 是 **保留的 K8s VolumeSnapshot 对象**，并把 provider handle 记录在 `snapshot_provider_id`。

## 5. 快照与恢复链路

### Snapshot 链路

后台编排器是 `StorageSnapshotOrchestrator`，它按下面的顺序推进：

1. 校验 `VolumeSnapshotClass` 存在
2. 如果是 `ready` 发起的 snapshot，先等待 CR 真正进入 `STOPPED`
3. 从 workspace PVC 创建 `VolumeSnapshot`
4. 等待 snapshot `readyToUse=true`
5. 读取 `VolumeSnapshotContent.status.snapshotHandle`
6. 显式删除 Sandbox CR
7. 显式删除 workspace PVC
8. 确认 CR/PVC/PV 都已消失
9. 把 sandbox 切到：
   - `status=cold`
   - `storage_backend_mode=standard_snapshot`
   - `pending_operation=null`

这里有两个刻意的实现细节：

- 不依赖 agent-sandbox 的隐式 shutdown 语义去回收磁盘
- 必须同时满足“快照 ready”和“live disk 确认释放”才允许 cutover 到 `cold`

### Restore 链路

恢复路径复用 direct sandbox 创建逻辑，但 `volumeClaimTemplates` 会带上：

- `spec.dataSource.kind=VolumeSnapshot`
- `spec.dataSource.apiGroup=snapshot.storage.k8s.io`

恢复顺序是：

1. 校验 snapshot backend ready
2. 创建新的 direct Sandbox CR
3. `workspace` PVC 从绑定 snapshot 恢复
4. 等待 PVC/PV materialize
5. 若目标是 `restore only`，等待 CR 落到 `STOPPED`
6. 若目标是 `start on cold`，等待 CR 落到 `READY`
7. 切回：
   - `storage_backend_mode=live_disk`
   - `pending_operation=null`
8. 尝试删除旧的 bound snapshot

## 6. 失败补偿与这次修过的边界问题

这次实现里，review 后特别补了 4 个关键保护：

### 1. 不会对还没真正停稳的 sandbox 做 snapshot

`snapshot(ready)` 不再只是“发出 stop 请求后立刻快照”。

后台会先读真实 Sandbox CR：

- 如果 K8s 还显示 `READY`
- 或者还在 `creating`

那么只会继续等待，不会创建 VolumeSnapshot。

### 2. restore 后遗留的旧 snapshot 不会被错误复用

如果 restore 成功但旧 snapshot 清理失败，sandbox 会回到 `live_disk`，但保留 snapshot binding。

这时候下一次再做 `snapshot`，当前实现会先尝试清理旧 snapshot：

- 清理成功：再创建新 snapshot
- 清理失败：本次 snapshot 直接失败，保持 `stopped/live_disk`

也就是说，不会把旧 snapshot 当成“新的冷存点”继续复用。

### 3. restore 遇到运行时错误不会无限卡在 `restoring`

`k8s_sync` 在 `pending_operation` 期间会抑制普通状态回写，因此 restore 不能依赖 sync loop 自动把 `ERROR` 写回 DB。

这次在 orchestrator 里显式补了处理：

- 如果 workspace 已 materialize，但 CR 进入 `ReconcilerError`
- sandbox 会回落到 `stopped/live_disk`
- 用户可以重试 `start`

这样不会无限停在 `cold + restoring`。

### 4. 删除 live-disk sandbox 时，bound snapshot 清理失败不会再伪装成删除成功

现在 delete 路径会先尝试清理残留的 bound snapshot。

如果 snapshot 清理失败：

- 不会继续删 live CR/PVC
- sandbox 会被标成 `error`
- API 返回 `409`

因此不会出现“接口返回 204，但后台留下孤儿 snapshot”的情况。

## 7. Metering 与 quota 语义

这次没有引入新的 quota 资源类型，仍然沿用已有 `StorageLedger`。

但 `StorageLedger` 新增了：

- `backend_mode`

它和 sandbox 的 `storage_backend_mode` 对齐，当前值可能是：

- `live_disk`
- `standard_snapshot`

这意味着：

- `cold` sandbox 仍然占用 storage quota
- 只有真正 `delete sandbox` 才 release storage ledger
- 但冷存后不再占用 compute session

## 8. 后台循环与状态同步

为避免把 provider 级 snapshot 状态机塞进已有 metering/lifecycle loop，这次单独新增了 storage snapshot tick：

- 单副本模式：`treadstone/main.py`
- 多副本模式：`LeaderControlledSyncSupervisor`

它只负责扫描：

- `pending_operation=snapshotting`
- `pending_operation=restoring`

并推进 cold storage 编排。

同时 `k8s_sync` 这次有两个重要调整：

- `cold` 被视为“CR 缺失也合法”
- `pending_operation` 非空时，watch/reconcile 不会覆盖 orchestrator 正在推进的状态

## 9. 当前边界

这一版明确只实现了下面这组能力：

- 只支持 `persist=true` 的 direct sandbox
- 只支持单 workspace 卷
- 只支持一份绑定 snapshot
- 不支持 clone / fork
- 不支持多历史恢复点
- 不支持跨 sandbox restore
- `archive_snapshot` 只在 schema 里预留，功能未启用

因此它解决的是：

- 持久 sandbox 的冷存与恢复
- live disk 成本释放
- 从“绑定在原 AZ 的 PVC”切到“从 snapshot 重新 materialize 的 PVC”

但它还不是“完全透明的 Neon 风格 auto-resume 平台”。后续如果继续演进，顺序仍然建议是：

1. `auto-stop`
2. `auto-snapshot-to-cold`
3. `auto-archive`
4. `auto-delete`
5. 代理入口透明恢复
