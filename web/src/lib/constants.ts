export const SANDBOX_STATUSES = ["creating", "ready", "stopped", "error", "deleting"] as const
export type SandboxStatus = (typeof SANDBOX_STATUSES)[number]

export const USER_ROLES = ["admin", "rw", "ro"] as const
export type UserRole = (typeof USER_ROLES)[number]

export const DATA_PLANE_MODES = ["none", "all", "selected"] as const
export type DataPlaneMode = (typeof DATA_PLANE_MODES)[number]

export const GRANT_STATUSES = ["active", "exhausted", "expired"] as const
export type GrantStatus = (typeof GRANT_STATUSES)[number]

export const COMPUTE_SESSION_STATUSES = ["active", "completed"] as const
export type ComputeSessionStatus = (typeof COMPUTE_SESSION_STATUSES)[number]
