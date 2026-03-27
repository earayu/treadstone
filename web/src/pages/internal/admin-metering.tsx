import { useState } from "react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
  useTierTemplates,
  useAdminUserUsage,
  useAdminUpdatePlan,
  useAdminCreateGrant,
  useAdminBatchGrants,
  type TierTemplate,
} from "@/api/admin"

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  return `${h} hr`
}

function TierTemplatesSection() {
  const { data, isLoading, isError, refetch } = useTierTemplates()
  const tiers = data?.items ?? []

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
                <TierRow key={tier.tier} tier={tier} odd={idx % 2 === 1} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TierRow({ tier, odd }: { tier: TierTemplate; odd: boolean }) {
  return (
    <tr className={cn("border-b border-border/15", odd && "bg-[hsl(0,0%,4%)]")}>
      <td className="px-5 py-3 text-xs font-medium text-primary">{tier.tier}</td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.compute_credits_monthly} vCPU-h
      </td>
      <td className="px-5 py-3 text-xs text-foreground">
        {tier.storage_credits_monthly} GiB
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{tier.max_concurrent_running}</td>
      <td className="px-5 py-3 text-xs text-foreground">
        {formatDuration(tier.max_sandbox_duration_seconds)}
      </td>
      <td className="px-5 py-3 text-xs text-foreground">{tier.grace_period_seconds}s</td>
      <td className="px-5 py-3">
        <button
          title="Edit tier template"
          className="rounded-sm border border-border/40 px-3 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-accent"
        >
          Edit
        </button>
      </td>
    </tr>
  )
}

function UserPlanSection() {
  const [inputId, setInputId] = useState("")
  const [lookupId, setLookupId] = useState<string | null>(null)
  const { data: usage, isLoading, error } = useAdminUserUsage(lookupId)
  const updatePlan = useAdminUpdatePlan()
  const createGrant = useAdminCreateGrant()

  const handleLookup = () => {
    const trimmed = inputId.trim()
    if (trimmed) setLookupId(trimmed)
  }

  const handleChangeTier = (newTier: string) => {
    if (!lookupId) return
    updatePlan.mutate(
      { userId: lookupId, body: { tier: newTier } },
      {
        onSuccess: () => toast.success(`Tier updated to ${newTier}`),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const handleGrantCredits = () => {
    if (!lookupId) return
    createGrant.mutate(
      {
        userId: lookupId,
        body: { credit_type: "compute", amount: 50, grant_type: "admin_grant" },
      },
      {
        onSuccess: () => toast.success("Credits granted"),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const tier = usage?.tier ?? "—"
  const computeUsed = usage?.compute.monthly_used
  const computeLimit = usage?.compute.monthly_limit
  const creditsRemaining =
    computeUsed != null && computeLimit != null ? (computeLimit - computeUsed).toFixed(1) : "—"
  const maxConcurrent = usage?.limits.max_concurrent_running ?? "—"
  const runningNow = usage?.limits.current_running ?? 0

  return (
    <div className="border border-border/20 bg-black rounded">
      <div className="flex items-center gap-4 border-b border-border/20 bg-card px-5 py-4">
        <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
          USER PLAN MANAGEMENT
        </span>
        <span className="text-[11px] text-muted-foreground/50">
          — lookup · change tier · apply overrides · issue credits
        </span>
      </div>

      <div className="flex items-center gap-3 border-b border-border/15 px-5 py-3">
        <label className="text-[11px] font-medium text-muted-foreground">User ID</label>
        <input
          type="text"
          value={inputId}
          onChange={(e) => setInputId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLookup()}
          placeholder="usr-xxxx-yyyy-zzzz"
          className="h-[34px] w-[400px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          onClick={handleLookup}
          className="h-[34px] rounded-sm bg-accent px-5 text-xs font-medium text-foreground transition-colors hover:bg-accent/80"
        >
          Lookup
        </button>
      </div>

      {lookupId && (
        <div className="m-5 rounded-sm border border-border/20 bg-background p-5">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Looking up user…</p>
          ) : error ? (
            <p className="text-sm text-destructive">User not found or error occurred.</p>
          ) : (
            <>
              <div className="grid grid-cols-4 gap-6">
                <div>
                  <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                    CURRENT TIER
                  </p>
                  <p className="mt-1 text-base font-bold text-primary">{tier}</p>
                </div>
                <div>
                  <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                    COMPUTE USED
                  </p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {computeUsed != null && computeLimit != null
                      ? `${computeUsed.toFixed(1)} / ${computeLimit.toFixed(1)} vCPU-h`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                    CREDITS REMAINING
                  </p>
                  <p className="mt-1 text-base font-semibold text-foreground">{creditsRemaining}</p>
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

              <div className="mt-6 flex gap-3">
                <button
                  onClick={() => handleChangeTier("pro")}
                  disabled={updatePlan.isPending}
                  className="rounded-sm border border-border/40 px-4 py-1.5 text-[11px] font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Change Tier to Pro
                </button>
                <button
                  disabled
                  className="rounded-sm border border-border/40 px-4 py-1.5 text-[11px] font-medium text-foreground opacity-50"
                >
                  Apply Overrides
                </button>
                <button
                  onClick={handleGrantCredits}
                  disabled={createGrant.isPending}
                  className="rounded-sm border border-border/40 px-4 py-1.5 text-[11px] font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Grant Credits
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function BatchGrantsSection() {
  const [userIds, setUserIds] = useState("")
  const [creditType, setCreditType] = useState<"compute" | "storage">("compute")
  const [amount, setAmount] = useState("50.0")
  const [grantType, setGrantType] = useState("campaign")
  const batchGrants = useAdminBatchGrants()

  const handleSubmit = () => {
    const ids = userIds
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
    if (ids.length === 0) {
      toast.error("Please provide at least one user ID.")
      return
    }
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) {
      toast.error("Amount must be a positive number.")
      return
    }
    batchGrants.mutate(
      { user_ids: ids, credit_type: creditType, amount: amt, grant_type: grantType },
      {
        onSuccess: (res) =>
          toast.success(`Batch grant complete: ${res.succeeded}/${res.total_requested} succeeded`),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <div className="border border-border/20 bg-black rounded">
      <div className="flex items-center gap-4 border-b border-border/20 bg-card px-5 py-4">
        <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
          BATCH CREDIT GRANTS
        </span>
        <span className="text-[11px] text-muted-foreground/50">
          — issue credits to multiple users at once
        </span>
      </div>

      <div className="p-5">
        <div className="flex gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-muted-foreground">
              User IDs (one per line)
            </label>
            <textarea
              rows={3}
              value={userIds}
              onChange={(e) => setUserIds(e.target.value)}
              placeholder={"usr-aaaa-bbbb\nusr-cccc-dddd\n..."}
              className="h-[72px] w-[340px] resize-none rounded-sm border border-border/40 bg-card px-3 py-2 text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-muted-foreground">Credit Type</label>
            <select
              value={creditType}
              onChange={(e) => setCreditType(e.target.value as "compute" | "storage")}
              className="h-[34px] w-[140px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="compute">compute</option>
              <option value="storage">storage</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-muted-foreground">
              Amount (vCPU-h)
            </label>
            <input
              type="text"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="h-[34px] w-[100px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-muted-foreground">Grant Type</label>
            <select
              value={grantType}
              onChange={(e) => setGrantType(e.target.value)}
              className="h-[34px] w-[130px] rounded-sm border border-border/40 bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="campaign">campaign</option>
              <option value="admin_grant">admin_grant</option>
              <option value="support">support</option>
            </select>
          </div>

          <div className="flex flex-col justify-end">
            <button
              onClick={handleSubmit}
              disabled={batchGrants.isPending}
              className="h-[34px] rounded-sm bg-primary px-5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              Run Batch Grant
            </button>
          </div>
        </div>

        <p className="mt-4 text-[11px] text-warning">
          ⚠ This action issues credits to all listed users. Double-check before submitting.
        </p>
      </div>
    </div>
  )
}

export function AdminMeteringPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">Admin Metering</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Manage tier templates, user plans, and credit grants.
        </p>
      </div>

      <TierTemplatesSection />
      <UserPlanSection />
      <BatchGrantsSection />
    </div>
  )
}
