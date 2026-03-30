import { useRef, useState } from "react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { formatSeconds } from "@/lib/format-time"
import { formatTierDisplayName } from "@/lib/tier-label"
import {
  useTierTemplates,
  useUpdateTierTemplate,
  useLookupUserByEmail,
  useAdminUserUsage,
  useAdminUpdatePlan,
  useAdminCreateComputeGrant,
  useAdminCreateStorageGrant,
  useAdminListWaitlist,
  useAdminUpdateWaitlistApplication,
  type TierTemplate,
  type WaitlistApplication,
} from "@/api/admin"


interface EditTierDialogProps {
  tier: TierTemplate
  onClose: () => void
}

function EditTierDialog({ tier, onClose }: EditTierDialogProps) {
  const updateTierTemplate = useUpdateTierTemplate()

  const [compute, setCompute] = useState(String(tier.compute_units_monthly))
  const [storage, setStorage] = useState(String(tier.storage_capacity_gib))
  const [maxConcurrent, setMaxConcurrent] = useState(String(tier.max_concurrent_running))
  const [maxDurationNever, setMaxDurationNever] = useState(tier.max_sandbox_duration_seconds === 0)
  const [maxDuration, setMaxDuration] = useState(
    tier.max_sandbox_duration_seconds === 0 ? "" : String(tier.max_sandbox_duration_seconds),
  )
  const [gracePeriod, setGracePeriod] = useState(String(tier.grace_period_seconds))
  const [allowedTemplates, setAllowedTemplates] = useState(tier.allowed_templates.join(", "))
  const [applyToExisting, setApplyToExisting] = useState(false)

  const handleSave = () => {
    const computeVal = parseFloat(compute)
    const storageVal = parseFloat(storage)
    const maxConcurrentVal = parseInt(maxConcurrent, 10)
    const maxDurationVal = maxDurationNever ? 0 : parseInt(maxDuration, 10)
    const gracePeriodVal = parseInt(gracePeriod, 10)

    if (
      isNaN(computeVal) ||
      isNaN(storageVal) ||
      isNaN(maxConcurrentVal) ||
      (!maxDurationNever && isNaN(maxDurationVal)) ||
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
          toast.success(`Tier "${formatTierDisplayName(tier.tier)}" updated successfully.`)
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
            <span className="text-primary">{formatTierDisplayName(tier.tier)}</span>
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
                Max Auto-Stop Interval (seconds)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  disabled={maxDurationNever}
                  value={maxDurationNever ? "" : maxDuration}
                  placeholder={maxDurationNever ? "Never" : undefined}
                  onChange={(e) => setMaxDuration(e.target.value)}
                  className="h-[34px] flex-1 rounded-sm border border-border/40 bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                />
                <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={maxDurationNever}
                    onChange={(e) => setMaxDurationNever(e.target.checked)}
                    className="h-3.5 w-3.5 rounded-sm border border-border/40 bg-background accent-primary"
                  />
                  <span className="text-[11px] text-muted-foreground">Never</span>
                </label>
              </div>
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
    { label: "MAX AUTO-STOP", className: "w-[15%]" },
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
      <td className="px-5 py-3 text-xs font-medium text-primary">
        {formatTierDisplayName(tier.tier)}
      </td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.compute_units_monthly} CU-h
      </td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.storage_capacity_gib} GiB
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{tier.max_concurrent_running}</td>
      <td className="px-5 py-3 text-xs text-foreground">
        {formatSeconds(tier.max_sandbox_duration_seconds)}
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{formatSeconds(tier.grace_period_seconds)}</td>
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

function UserPlanSection({ defaultEmail = "" }: { defaultEmail?: string }) {
  const [inputEmail, setInputEmail] = useState(defaultEmail)
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
                    <p className="mt-1 text-base font-bold text-primary">
                      {tier === "—" ? "—" : formatTierDisplayName(tier)}
                    </p>
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
                          <option key={t} value={t}>
                            {formatTierDisplayName(t)}
                          </option>
                        ))
                      ) : (
                        <option value={tier}>{formatTierDisplayName(tier)}</option>
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
                      type="text"
                      placeholder="YYYY-MM-DD"
                      value={computeExpiresAt}
                      onChange={(e) => setComputeExpiresAt(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
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
                      type="text"
                      placeholder="YYYY-MM-DD"
                      value={storageExpiresAt}
                      onChange={(e) => setStorageExpiresAt(e.target.value)}
                      className="h-[34px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>
                  <div className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-4">
                    <label className="text-[10px] font-medium text-muted-foreground">Reason (optional)</label>
                    <input
                      type="text"
                      value={storageReason}
                      onChange={(e) => setStorageReason(e.target.value)}
                      placeholder="e.g. Storage addon for Custom Plan trial"
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

function WaitlistApplicationsSection({ onLookupEmail }: { onLookupEmail: (email: string) => void }) {
  const [tierFilter, setTierFilter] = useState<string>("")
  const [statusFilter, setStatusFilter] = useState<string>("pending")
  const { data, isLoading, isError, refetch } = useAdminListWaitlist({
    tier: tierFilter || undefined,
    status: statusFilter || undefined,
  })
  const updateApplication = useAdminUpdateWaitlistApplication()

  const items: WaitlistApplication[] = data?.items ?? []
  const total = data?.total ?? 0

  const handleUpdateStatus = (applicationId: string, status: "approved" | "rejected") => {
    updateApplication.mutate(
      { applicationId, status },
      {
        onSuccess: () => toast.success(`Application marked as ${status}`),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const columns = [
    { label: "NAME / EMAIL", className: "w-[22%]" },
    { label: "TIER", className: "w-[8%]" },
    { label: "COMPANY", className: "w-[14%]" },
    { label: "USE CASE", className: "w-[24%]" },
    { label: "STATUS", className: "w-[10%]" },
    { label: "SUBMITTED", className: "w-[12%]" },
    { label: "ACTIONS", className: "w-[10%]" },
  ] as const

  return (
    <div className="border border-border/20 bg-black rounded">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-4 border-b border-border/20 bg-card px-5 py-4">
        <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
          WAITLIST APPLICATIONS
        </span>
        <span className="text-[11px] text-muted-foreground/50">— {total} total</span>
        <div className="ml-auto flex items-center gap-3">
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="h-[28px] rounded-sm border border-border/40 bg-card px-2 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All tiers</option>
            <option value="pro">Pro</option>
            <option value="ultra">Ultra</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-[28px] rounded-sm border border-border/40 bg-card px-2 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[800px]">
          <thead>
            <tr className="border-b border-border/20 bg-card">
              {columns.map((col) => (
                <th
                  key={col.label}
                  className={cn(
                    "px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground",
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
                  Failed to load waitlist applications.{" "}
                  <button onClick={() => refetch()} className="underline hover:text-destructive/80">
                    Retry
                  </button>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-muted-foreground">
                  No applications found.
                </td>
              </tr>
            ) : (
              items.map((item, idx) => (
                <tr
                  key={item.id}
                  className={cn(
                    "border-b border-border/10 text-xs",
                    idx % 2 === 1 ? "bg-card/30" : "bg-transparent",
                  )}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{item.name}</div>
                    <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{item.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                        item.target_tier === "pro"
                          ? "bg-primary/10 text-primary"
                          : "bg-purple-500/10 text-purple-400",
                      )}
                    >
                      {item.target_tier}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{item.company ?? "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    <span className="line-clamp-2">{item.use_case ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                        item.status === "approved"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : item.status === "rejected"
                            ? "bg-destructive/10 text-destructive"
                            : "bg-muted/40 text-muted-foreground",
                      )}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {new Date(item.gmt_created).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        onClick={() => onLookupEmail(item.email)}
                        className="rounded-sm border border-border/40 px-2 py-1 text-[10px] font-medium text-foreground transition-colors hover:bg-accent"
                      >
                        Lookup
                      </button>
                      {item.status === "pending" && (
                        <>
                          <button
                            onClick={() => handleUpdateStatus(item.id, "approved")}
                            disabled={updateApplication.isPending}
                            className="rounded-sm bg-emerald-600/80 px-2 py-1 text-[10px] font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleUpdateStatus(item.id, "rejected")}
                            disabled={updateApplication.isPending}
                            className="rounded-sm bg-destructive/70 px-2 py-1 text-[10px] font-medium text-white transition-colors hover:bg-destructive disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function AdminMeteringPage() {
  const [lookupEmail, setLookupEmail] = useState("")
  const [lookupKey, setLookupKey] = useState(0)
  const userPlanRef = useRef<HTMLDivElement>(null)

  const handleLookupEmail = (email: string) => {
    setLookupEmail(email)
    setLookupKey((k) => k + 1)
    userPlanRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">Admin Metering</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Manage tier templates, user plans, and Compute Unit grants.
        </p>
      </div>

      <TierTemplatesSection />
      <div ref={userPlanRef}>
        <UserPlanSection key={lookupKey} defaultEmail={lookupEmail} />
      </div>
      <WaitlistApplicationsSection onLookupEmail={handleLookupEmail} />
    </div>
  )
}
