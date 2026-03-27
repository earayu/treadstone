export function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Overview of your sandboxes, usage, and account status.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {["Current Tier", "Compute Remaining", "Running Sandboxes", "API Keys"].map((label) => (
          <div key={label} className="rounded-md border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="mt-1 text-xl font-semibold text-foreground">—</div>
          </div>
        ))}
      </div>
    </div>
  )
}
