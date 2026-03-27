export function LandingPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-20">
      <h1 className="text-4xl font-bold tracking-tight text-foreground">
        Agent-native sandbox platform
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
        Run code, build projects, deploy environments, and hand off browser sessions.
        Open source and self-hostable.
      </p>
      <div className="mt-8 flex gap-4">
        <a href="/auth/sign-up" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
          Start free
        </a>
        <a href="/quickstart" className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground">
          Read docs
        </a>
      </div>
    </div>
  )
}
