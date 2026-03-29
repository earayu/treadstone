import { useState } from "react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
  useTierTemplates,
  useUpdateTierTemplate,
  useLookupUserByEmail,
  useAdminUserUsage,
  useAdminUpdatePlan,
  useAdminCreateComputeGrant,
  useAdminCreateStorageGrant,
  type TierTemplate,
} from "@/api/admin"

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  return `${h} hr`
}

interface EditTierDialogProps {
  tier: TierTemplate
  onClose: () => void
}

function EditTierDialog({ tier, onClose }: EditTierDialogProps) {
  const updateTierTemplate = useUpdateTierTemplate()

  const [compute, setCompute] = useState(String(tier.compute_units_monthly))
  const [storage, setStorage] = useState(String(tier.storage_capacity_gib))
  const [maxConcurrent, setMaxConcurrent] = useState(String(tier.max_concurrent_running))
  const [maxDuration, setMaxDuration] = useState(String(tier.max_sandbox_duration_seconds))
  const [gracePeriod, setGracePeriod] = useState(String(tier.grace_period_seconds))
  const [allowedTemplates, setAllowedTemplates] = useState(tier.allowed_templates.join(", "))
  const [applyToExisting, setApplyToExisting] = useState(false)

  const handleSave = () => {
    const computeVal = parseFloat(compute)
    const storageVal = parseFloat(storage)
    const maxConcurrentVal = parseInt(maxConcurrent, 10)
    const maxDurationVal = parseInt(maxDuration, 10)
    const gracePeriodVal = parseInt(gracePeriod, 10)

    if (
      isNaN(computeVal) ||
      isNaN(storageVal) ||
      isNaN(maxConcurrentVal) ||
      isNaN(maxDurationVal) ||
      isNaN(gracePeriodVal)
    ) {
      toast.error("All numeric fields must be valid numbers.")
      return
    }

    const templates = allowedTemplates
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)

    updateTierTemplate.mutate(
      {
        tierName: tier.tier,
        body: {
          compute_units_monthly: computeVal,
          storage_capacity_gib: storageVal,
          max_concurrent_running: maxConcurrentVal,
          max_sandbox_duration_seconds: maxDurationVal,
          grace_period_seconds: gracePeriodVal,
          allowed_templates: templates,
          apply_to_existing: applyToExisting,
        },
      },
      {
        onSuccess: () => {
          toast.success(`Tier "${tier.tier}" updated successfully.`)
          onClose()
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-[480px] rounded border border-border/30 bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/20 px-5 py-4">
          <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
            EDIT TIER TEMPLATE —{" "}
            <span className="text-primary">{tier.tier}</span>
          </span>
          <button
            onClick={onClose}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Compute quota / month
              </label>
              <input
                type="number"
                value={compute}
                onChange={(e) => setCompute(e.target.value)}
                className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Storage capacity (GiB)
              </label>
              <input
                type="number"
                value={storage}
                onChange={(e) => setStorage(e.target.value)}
                className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Max Concurrent Running
              </label>
              <input
                type="number"
                value={maxConcurrent}
                onChange={(e) => setMaxConcurrent(e.target.value)}
                className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Max Sandbox Duration (seconds)
              </label>
              <input
                type="number"
                value={maxDuration}
                onChange={(e) => setMaxDuration(e.target.value)}
                className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Grace Period (seconds)
              </label>
              <input
                type="number"
                value={gracePeriod}
                onChange={(e) => setGracePeriod(e.target.value)}
                className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-muted-foreground">
              Allowed Templates (comma-separated)
            </label>
            <input
              type="text"
              value={allowedTemplates}
              onChange={(e) => setAllowedTemplates(e.target.value)}
              placeholder="aio-sandbox-tiny, aio-sandbox-small, ..."
              className="h-[34px] rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={applyToExisting}
              onChange={(e) => setApplyToExisting(e.target.checked)}
              className="h-3.5 w-3.5 rounded-sm border border-border/40 bg-background accent-primary"
            />
            <span className="text-[11px] text-muted-foreground">
              Apply limits to existing users on this tier
            </span>
          </label>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-border/20 px-5 py-4">
          <button
            onClick={onClose}
            className="rounded-sm border border-border/40 px-4 py-1.5 text-[11px] font-medium text-foreground transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={updateTierTemplate.isPending}
            className="rounded-sm bg-primary px-5 py-1.5 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {updateTierTemplate.isPending ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  )
}

function TierTemplatesSection() {
  const { data, isLoading, isError, refetch } = useTierTemplates()
  const tiers = data?.items ?? []
  const [editingTier, setEditingTier] = useState<TierTemplate | null>(null)

  const columns = [
    { label: "TIER", className: "w-[12%]" },
    { label: "COMPUTE / MO", className: "w-[15%]" },
    { label: "STORAGE / MO", className: "w-[15%]" },
    { label: "MAX CONCURRENT", className: "w-[16%]" },
    { label: "MAX DURATION", className: "w-[15%]" },
    { label: "GRACE PERIOD", className: "w-[15%]" },
    { label: "ACTIONS", className: "w-[12%]" },
  ] as const

  return (
    <>
      {editingTier && (
        <EditTierDialog tier={editingTier} onClose={() => setEditingTier(null)} />
      )}
      <div className="border border-border/20 bg-black rounded">
        <div className="border-b border-border/20 bg-card px-5 py-4">
          <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
            TIER TEMPLATES
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-border/20 bg-card">
                {columns.map((col) => (
                  <th
                    key={col.label}
                    className={cn(
                      "px-5 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground",
                      col.className,
                    )}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-sm text-destructive">
                    Failed to load tier templates.{" "}
                    <button onClick={() => refetch()} className="underline hover:text-destructive/80">
                      Retry
                    </button>
                  </td>
                </tr>
              ) : tiers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-sm text-muted-foreground">
                    No tier templates configured.
                  </td>
                </tr>
              ) : (
                tiers.map((tier, idx) => (
                  <TierRow key={tier.tier} tier={tier} odd={idx % 2 === 1} onEdit={setEditingTier} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function TierRow({
  tier,
  odd,
  onEdit,
}: {
  tier: TierTemplate
  odd: boolean
  onEdit: (tier: TierTemplate) => void
}) {
  return (
    <tr className={cn("border-b border-border/15", odd && "bg-[hsl(0,0%,4%)]")}>
      <td className="px-5 py-3 text-xs font-medium text-primary">{tier.tier}</td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.compute_units_monthly} CU-h
      </td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.storage_capacity_gib} GiB
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{tier.max_concurrent_running}</td>
      <td className="px-5 py-3 text-xs text-foreground">
        {formatDuration(tier.max_sandbox_duration_seconds)}
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{tier.grace_period_seconds}s</td>
      <td className="px-5 py-3">
        <button
          title="Edit tier template"
          onClick={() => onEdit(tier)}
          className="rounded-sm border border-border/40 px-3 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-accent"
        >
          Edit
        </button>
      </td>
    </tr>
  )
}

const GRANT_TYPES = ["admin_grant", "welcome_bonus", "campaign", "support"] as const
type GrantType = (typeof GRANT_TYPES)[number]

function UserPlanSection() {
  const [inputEmail, setInputEmail] = useState("")
  const [resolvedUserId, setResolvedUserId] = useState<string | null>(null)
  const [resolvedEmail, setResolvedEmail] = useState<string | null>(null)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const lookupByEmail = useLookupUserByEmail()
  const { data: usage, isLoading, error } = useAdminUserUsage(resolvedUserId)
  const { data: tierTemplatesData } = useTierTemplates()
  const availableTiers = tierTemplatesData?.items?.map((t) => t.tier) ?? []
  const updatePlan = useAdminUpdatePlan()
  const createComputeGrant = useAdminCreateComputeGrant()
  const createStorageGrant = useAdminCreateStorageGrant()
  const [selectedTier, setSelectedTier] = useState("")

  // Compute grant fields
  const [computeAmount, setComputeAmount] = useState("50")
  const [computeGrantType, setComputeGrantType] = useState<GrantType>("admin_grant")
  const [computeReason, setComputeReason] = useState("")
  const [computeCampaignId, setComputeCampaignId] = useState("")
  const [computeExpiresAt, setComputeExpiresAt] = useState("")

  // Storage grant fields
  const [storageGib, setStorageGib] = useState("10")
  const [storageGrantType, setStorageGrantType] = useState<GrantType>("admin_grant")
  const [storageReason, setStorageReason] = useState("")
  const [storageCampaignId, setStorageCampaignId] = useState("")
  const [storageExpiresAt, setStorageExpiresAt] = useState("")

  const handleLookup = () => {
    const trimmed = inputEmail.trim()
    if (!trimmed) return
    setLookupError(null)
    lookupByEmail.mutate(trimmed, {
      onSuccess: (res) => {
        setResolvedUserId(res.user_id)
        setResolvedEmail(res.email)
        setLookupError(null)
      },
      onError: () => {
        setResolvedUserId(null)
        setResolvedEmail(null)
        setSelectedTier("")
        setLookupError(`No user found for "${trimmed}"`)
      },
    })
  }

  const handleChangeTier = (newTier: string) => {
    if (!resolvedUserId) return
    updatePlan.mutate(
      { userId: resolvedUserId, body: { tier: newTier } },
      {
        onSuccess: () => toast.success(`Tier updated to ${newTier}`),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const handleGrantCompute = () => {
    if (!resolvedUserId) return
    const amt = parseFloat(computeAmount)
    if (isNaN(amt) || amt <= 0) {
      toast.error("Compute amount must be a positive number.")
      return
    }
    createComputeGrant.mutate(
      {
        userId: resolvedUserId,
        body: {
          amount: amt,
          grant_type: computeGrantType,
          reason: computeReason.trim() || null,
          campaign_id: computeGrantType === "campaign" ? computeCampaignId.trim() || null : null,
          expires_at: computeExpiresAt ? new Date(computeExpiresAt).toISOString() : null,
        },
      },
      {
        onSuccess: () => {
          toast.success("Compute grant created")
          setComputeReason("")
          setComputeCampaignId("")
          setComputeExpiresAt("")
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const handleGrantStorage = () => {
    if (!resolvedUserId) return
    const gib = parseInt(storageGib, 10)
    if (isNaN(gib) || gib <= 0) {
      toast.error("Storage size (GiB) must be a positive integer.")
      return
    }
    createStorageGrant.mutate(
      {
        userId: resolvedUserId,
        body: {
          size_gib: gib,
          grant_type: storageGrantType,
          reason: storageReason.trim() || null,
          campaign_id: storageGrantType === "campaign" ? storageCampaignId.trim() || null : null,
          expires_at: storageExpiresAt ? new Date(storageExpiresAt).toISOString() : null,
        },
      },
      {
        onSuccess: () => {
          toast.success("Storage quota grant created")
          setStorageReason("")
          setStorageCampaignId("")
          setStorageExpiresAt("")
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const tier = usage?.tier ?? "—"
  const cuHours = usage?.compute.compute_unit_hours ?? 0
  const maxConcurrent = usage?.limits.max_concurrent_running ?? "—"
  const runningNow = usage?.limits.current_running ?? 0

  return (
    <div className="border border-border/20 bg-black rounded">
      <div className="flex items-center gap-4 border-b border-border/20 bg-card px-5 py-4">
        <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
          USER PLAN MANAGEMENT
        </span>
        <span className="text-[11px] text-muted-foreground/50">
          — lookup · change tier · issue grants
        </span>
      </div>

      <div className="flex items-center gap-3 border-b border-border/15 px-5 py-3">
        <label className="text-[11px] font-medium text-muted-foreground">Email</label>
        <input
          type="email"
          value={inputEmail}
          onChange={(e) => setInputEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLookup()}
          placeholder="user@example.com"
          className="h-[34px] w-[400px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          onClick={handleLookup}
          disabled={lookupByEmail.isPending}
          className="h-[34px] rounded-sm bg-accent px-5 text-xs font-medium text-foreground transition-colors hover:bg-accent/80 disabled:opacity-50"
        >
          {lookupByEmail.isPending ? "Looking up…" : "Lookup"}
        </button>
      </div>

      {lookupError && (
        <div className="mx-5 mt-5 rounded-sm border border-destructive/30 bg-destructive/10 px-4 py-3">
          <p className="text-sm text-destructive">{lookupError}</p>
        </div>
      )}

      {resolvedUserId && (
        <div className="m-5 space-y-5">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading usage data…</p>
          ) : error ? (
            <p className="text-sm text-destructive">Failed to load usage data.</p>
          ) : (
            <>
              {/* User stats */}
              <div className="rounded-sm border border-border/20 bg-background p-5">
                <div className="mb-4 flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{resolvedEmail}</span>
                  <span className="text-muted-foreground/40">|</span>
                  <span className="font-mono text-[10px]">{resolvedUserId}</span>
                </div>
                <div className="grid grid-cols-3 gap-6">
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                      CURRENT TIER
                    </p>
                    <p className="mt-1 text-base font-bold capitalize text-primary">{tier}</p>
                  </div>
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                      CU-HOURS USED
                    </p>
                    <p className="mt-1 text-base font-semibold text-foreground">{cuHours.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                      RUNNING NOW
                    </p>
                    <p className="mt-1 text-base font-semibold text-foreground">
                      {runningNow} / {maxConcurrent}
                    </p>
                  </div>
                </div>
                <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-border/15 pt-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Change tier</label>
                    <select
                      value={selectedTier || tier}
                      onChange={(e) => setSelectedTier(e.target.value)}
                      className="h-[34px] w-[160px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {availableTiers.length > 0 ? (
                        availableTiers.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))
                      ) : (
                        <option value={tier}>{tier}</option>
                      )}
                    </select>
                  </div>
                  <button
                    onClick={() => handleChangeTier(selectedTier || tier)}
                    disabled={updatePlan.isPending || (selectedTier || tier) === tier}
                    className="h-[34px] rounded-sm bg-primary px-5 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
                  >
                    {updatePlan.isPending ? "Saving…" : "Apply tier"}
                  </button>
                </div>
              </div>

              {/* Compute grant */}
              <div className="rounded-sm border border-border/20 bg-background p-5">
                <p className="mb-4 text-[11px] font-medium uppercase tracking-wide text-primary">
                  Compute grant
                </p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Amount (CU-h)</label>
                    <input
                      type="text"
                      value={computeAmount}
                      onChange={(e) => setComputeAmount(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Grant type</label>
                    <select
                      value={computeGrantType}
                      onChange={(e) => setComputeGrantType(e.target.value as GrantType)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {GRANT_TYPES.map((gt) => (
                        <option key={gt} value={gt}>{gt}</option>
                      ))}
                    </select>
                  </div>
                  {computeGrantType === "campaign" && (
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] font-medium text-muted-foreground">Campaign ID</label>
                      <input
                        type="text"
                        value={computeCampaignId}
                        onChange={(e) => setComputeCampaignId(e.target.value)}
                        placeholder="e.g. launch-2026"
                        className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                  )}
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Expires at (optional)</label>
                    <input
                      type="date"
                      lang="en"
                      value={computeExpiresAt}
                      onChange={(e) => setComputeExpiresAt(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  <div className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-4">
                    <label className="text-[10px] font-medium text-muted-foreground">Reason (optional)</label>
                    <input
                      type="text"
                      value={computeReason}
                      onChange={(e) => setComputeReason(e.target.value)}
                      placeholder="e.g. Support request #1234"
                      className="h-[34px] w-full rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                </div>
                <div className="mt-3 flex justify-end">
                  <button
                    onClick={handleGrantCompute}
                    disabled={createComputeGrant.isPending}
                    className="h-[34px] rounded-sm bg-primary px-5 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                  >
                    {createComputeGrant.isPending ? "Granting…" : "Grant compute"}
                  </button>
                </div>
              </div>

              {/* Storage grant */}
              <div className="rounded-sm border border-border/20 bg-background p-5">
                <p className="mb-4 text-[11px] font-medium uppercase tracking-wide text-primary">
                  Storage quota grant
                </p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Size (GiB)</label>
                    <input
                      type="text"
                      value={storageGib}
                      onChange={(e) => setStorageGib(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Grant type</label>
                    <select
                      value={storageGrantType}
                      onChange={(e) => setStorageGrantType(e.target.value as GrantType)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {GRANT_TYPES.map((gt) => (
                        <option key={gt} value={gt}>{gt}</option>
                      ))}
                    </select>
                  </div>
                  {storageGrantType === "campaign" && (
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] font-medium text-muted-foreground">Campaign ID</label>
                      <input
                        type="text"
                        value={storageCampaignId}
                        onChange={(e) => setStorageCampaignId(e.target.value)}
                        placeholder="e.g. launch-2026"
                        className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                  )}
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-medium text-muted-foreground">Expires at (optional)</label>
                    <input
                      type="date"
                      lang="en"
                      value={storageExpiresAt}
                      onChange={(e) => setStorageExpiresAt(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  <div className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-4">
                    <label className="text-[10px] font-medium text-muted-foreground">Reason (optional)</label>
                    <input
                      type="text"
                      value={storageReason}
                      onChange={(e) => setStorageReason(e.target.value)}
                      placeholder="e.g. Storage addon for enterprise trial"
                      className="h-[34px] w-full rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                </div>
                <div className="mt-3 flex justify-end">
                  <button
                    onClick={handleGrantStorage}
                    disabled={createStorageGrant.isPending}
                    className="h-[34px] rounded-sm bg-primary px-5 text-[11px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                  >
                    {createStorageGrant.isPending ? "Granting…" : "Grant storage quota"}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function AdminMeteringPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">Admin Metering</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Manage tier templates, user plans, and Compute Unit grants.
        </p>
      </div>

      <TierTemplatesSection />
      <UserPlanSection />
    </div>
  )
}
