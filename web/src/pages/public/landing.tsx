import { useState } from "react"
import { Link } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"
import { TreadstoneSymbol } from "@/components/brand/logo"
import { useSubmitWaitlistApplication } from "@/api/admin"

const GITHUB_URL = "https://github.com/earayu/treadstone"
const RELEASES_URL = "https://github.com/earayu/treadstone/releases"
const PYPI_CLI_URL = "https://pypi.org/project/treadstone-cli/"
const SUPPORT_EMAIL = "support@treadstone-ai.dev"

const INSTALL_SH = "curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh"
const INSTALL_PS = "irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex"
const INSTALL_PIP = "pip install treadstone-cli"

type TerminalLine =
  | { kind: "comment"; text: string }
  | { kind: "cmd"; text: string }
  | { kind: "output"; text: string }
  | { kind: "gap" }

const SCENARIO: TerminalLine[] = [
  { kind: "comment", text: "# 1. Authenticate" },
  { kind: "cmd", text: "treadstone auth login --email agent@example.com --password ••••••••" },
  { kind: "output", text: "✓ Logged in as agent@example.com" },
  { kind: "gap" },
  { kind: "comment", text: "# 2. Pick a template" },
  { kind: "cmd", text: "treadstone --json templates list" },
  { kind: "output", text: '{ "items": [{ "name": "aio-sandbox-tiny", "cpu": "0.25", "memory": "512Mi" }, ...] }' },
  { kind: "gap" },
  { kind: "comment", text: "# 3. Create a sandbox — capture its ID" },
  { kind: "cmd", text: "treadstone --json sandboxes create --name agent-demo" },
  { kind: "output", text: '{ "id": "sb_3kx9m2p", "status": "running", "urls": { "proxy": "https://sb_3kx9m2p.proxy.treadstone-ai.dev" } }' },
  { kind: "gap" },
  { kind: "comment", text: "# 4. Hand the browser off to a human" },
  { kind: "cmd", text: "treadstone --json sandboxes web enable sb_3kx9m2p" },
  { kind: "output", text: '{ "open_link": "https://sb_3kx9m2p.web.treadstone-ai.dev?token=...", "expires_at": "2026-03-30T18:00:00Z" }' },
]

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "/month",
    desc: "Get started with lightweight sandboxes.",
    features: [
      "20\u00a0CU-h compute / month",
      "3 concurrent sandboxes",
      "aio-sandbox-tiny (0.25\u00a0core, 512\u00a0Mi)",
      "2\u00a0hr max auto-stop interval",
      "Sandbox lifecycle via CLI, SDK & API",
      "Browser hand-off sessions",
      "Community support",
    ],
    cta: "Get Started",
    ctaHref: "/auth/sign-up",
    highlighted: false,
    waitlistTier: null as string | null,
  },
  {
    name: "Pro",
    price: "Usage-based",
    period: "",
    tag: "COMING SOON",
    desc: "More compute, more concurrency, priority support.",
    features: [
      "120\u00a0CU-h compute / month",
      "8 concurrent sandboxes",
      "All templates up to aio-sandbox-medium",
      "15\u00a0GiB persistent storage",
      "24\u00a0hr max auto-stop interval",
      "Usage analytics & reporting",
      "Priority support",
    ],
    cta: "Apply for Free Access",
    ctaHref: null,
    highlighted: true,
    waitlistTier: "pro",
  },
  {
    name: "Ultra",
    price: "Usage-based",
    period: "",
    tag: "COMING SOON",
    desc: "Maximum compute and concurrency for heavy workloads.",
    features: [
      "400\u00a0CU-h compute / month",
      "20 concurrent sandboxes",
      "All templates up to aio-sandbox-xlarge",
      "50\u00a0GiB persistent storage",
      "72\u00a0hr max auto-stop interval",
      "Dedicated SLA & integrations",
    ],
    cta: "Apply for Free Access",
    ctaHref: null,
    highlighted: false,
    waitlistTier: "ultra",
  },
  {
    name: "Custom Plan",
    price: "Custom",
    period: "",
    desc: "Negotiated limits for teams and long-running workloads.",
    features: [
      "1,000\u00a0CU-h compute / month",
      "50 concurrent sandboxes",
      "100\u00a0GiB persistent storage",
      "7\u00a0day max auto-stop interval",
      "24\u00a0hr grace period",
      "All sandbox templates",
      "Contact us for terms & SLA",
    ],
    cta: "Contact Us",
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
    highlighted: false,
    waitlistTier: null as string | null,
  },
]

interface WaitlistDialogProps {
  tier: string
  onClose: () => void
}

function WaitlistDialog({ tier, onClose }: WaitlistDialogProps) {
  const submit = useSubmitWaitlistApplication()
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [company, setCompany] = useState("")
  const [useCase, setUseCase] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    submit.mutate(
      {
        email,
        name,
        target_tier: tier,
        company: company || undefined,
        use_case: useCase || undefined,
      },
      {
        onSuccess: () => setSubmitted(true),
        onError: (err) => setError(err.message),
      },
    )
  }

  const tierLabel = tier === "pro" ? "Pro" : "Ultra"

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md rounded-md border border-border/30 bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/20 px-5 py-4">
          <div>
            <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
              APPLY FOR FREE ACCESS —{" "}
            </span>
            <span className="text-[11px] font-bold uppercase tracking-[1.5px] text-primary">{tierLabel}</span>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            ✕
          </button>
        </div>

        {submitted ? (
          <div className="px-5 py-10 text-center">
            <p className="text-lg font-semibold text-primary">Application submitted!</p>
            <p className="mt-2 text-sm text-muted-foreground">
              We'll review your application and upgrade your account to the {tierLabel} plan shortly.
              Make sure you've signed up at{" "}
              <Link to="/auth/sign-up" className="text-primary underline" onClick={onClose}>
                treadstone-ai.dev
              </Link>{" "}
              using the same email.
            </p>
            <button
              onClick={onClose}
              className="mt-6 rounded bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 p-5">
            <p className="text-sm text-muted-foreground">
              We're granting free {tierLabel} access during our early launch. Fill in your details and we'll
              upgrade your account.
            </p>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Email <span className="text-destructive">*</span>
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="h-[36px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Name <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className="h-[36px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">Company (optional)</label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Your company or project"
                className="h-[36px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                How do you plan to use it? (optional)
              </label>
              <textarea
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                placeholder="e.g. Building AI coding agents that need isolated execution environments"
                rows={3}
                maxLength={1000}
                className="rounded-sm border border-border/40 bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring resize-none"
              />
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex items-center justify-end gap-3 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="rounded-sm border border-border/40 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submit.isPending}
                className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {submit.isPending ? "Submitting…" : "Submit Application"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function CodeBlock({ label, code }: { label: string; code: string }) {
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground/60">
        {label}
      </p>
      <pre className="overflow-x-auto rounded border border-border/20 bg-black/40 px-4 py-3 font-mono text-[12px] leading-relaxed text-foreground">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function TerminalScenario({ lines }: { lines: TerminalLine[] }) {
  return (
    <div className="overflow-hidden rounded border border-border/20 bg-black/40">
      {/* window chrome */}
      <div className="flex items-center gap-1.5 border-b border-border/20 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-border/40" />
        <span className="size-2.5 rounded-full bg-border/40" />
        <span className="size-2.5 rounded-full bg-border/40" />
        <span className="ml-3 font-mono text-[10px] text-muted-foreground/40">bash</span>
      </div>
      <pre className="overflow-x-auto px-5 py-5 font-mono text-[12px] leading-[1.85]">
        <code>
          {lines.map((line, i) => {
            if (line.kind === "gap") return <span key={i}>{"\n"}</span>
            if (line.kind === "comment")
              return (
                <span key={i} className="text-muted-foreground/40">
                  {line.text}
                  {"\n"}
                </span>
              )
            if (line.kind === "cmd")
              return (
                <span key={i}>
                  <span className="text-primary">$&nbsp;</span>
                  <span className="text-foreground">{line.text}</span>
                  {"\n"}
                </span>
              )
            return (
              <span key={i} className="text-emerald-400/70">
                {line.text}
                {"\n"}
              </span>
            )
          })}
        </code>
      </pre>
    </div>
  )
}

function Dot() {
  return <span className="mt-[5px] inline-block size-[5px] shrink-0 rounded-full bg-primary" aria-hidden="true" />
}

export function LandingPage() {
  const { data: user, isLoading } = useCurrentUser()
  const isLoggedIn = !isLoading && !!user
  const [waitlistTier, setWaitlistTier] = useState<string | null>(null)

  return (
    <div>
      {waitlistTier && (
        <WaitlistDialog tier={waitlistTier} onClose={() => setWaitlistTier(null)} />
      )}

      {/* ── Hero ──────────────────────────────────────────── */}
      <section className="flex flex-col items-center px-16 pb-24 pt-20 text-center">
        <h1 className="text-balance text-[clamp(3rem,8vw,5.5rem)] font-bold leading-[1.05] tracking-tight text-foreground">
          Sandbox
          <br />
          <span className="text-primary">for AI Agents</span>
        </h1>

        <p className="mt-6 max-w-lg text-balance text-base leading-relaxed text-muted-foreground">
          Run code, build software, and hand off browser sessions
          from isolated, agent-native environments.
        </p>

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {isLoggedIn ? (
            <Link
              to="/app"
              className="rounded bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Open Dashboard
            </Link>
          ) : (
            <Link
              to="/auth/sign-up"
              className="rounded bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Get Started
            </Link>
          )}
          <a
            href="#install-cli"
            className="rounded border border-border px-7 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Install CLI
          </a>
        </div>
      </section>

      <hr className="border-border/20" />

      {/* ── Command Line ──────────────────────────────────── */}
      <section id="install-cli" className="mx-auto grid max-w-[1280px] gap-16 px-16 py-20 md:grid-cols-[480px_1fr]">
        {/* Left: Install */}
        <div className="flex flex-col gap-7">
          <div>
            <h2 className="text-xl font-bold text-foreground">Install</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Install the CLI and start managing sandboxes in seconds. Works on macOS, Linux, and Windows.
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <CodeBlock label="macOS / Linux" code={INSTALL_SH} />
            <CodeBlock label="Windows PowerShell" code={INSTALL_PS} />
            <CodeBlock label="pip" code={INSTALL_PIP} />
          </div>

          <div className="flex flex-wrap gap-5 text-sm text-muted-foreground">
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
              GitHub&nbsp;→
            </a>
            <a href={RELEASES_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
              Releases&nbsp;→
            </a>
            <a href={PYPI_CLI_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
              PyPI&nbsp;→
            </a>
          </div>

          <p className="text-xs text-muted-foreground/60">
            Also available: <code className="font-mono">pip install treadstone-sdk</code>
          </p>
        </div>

        {/* Right: Usage */}
        <div className="flex flex-col gap-5">
          <div>
            <h2 className="text-xl font-bold text-foreground">Quickstart</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              A complete agent workflow in four commands — authenticate, discover, create, and hand off.
            </p>
          </div>

          <TerminalScenario lines={SCENARIO} />

          <div className="flex flex-wrap gap-3">
            {["CLI", "Python SDK", "REST API"].map((label) => (
              <span
                key={label}
                className="flex items-center gap-2 rounded border border-border/20 bg-card px-3.5 py-2 text-xs font-medium text-foreground"
              >
                <span className="inline-block size-[5px] rounded-full bg-primary" aria-hidden="true" />
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>

      <hr className="border-border/20" />

      {/* ── Plans ─────────────────────────────────────────── */}
      <section id="plans" className="bg-card/30 px-16 py-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="mb-12 text-center">
            <h2 className="text-balance text-2xl font-bold text-foreground">Plans</h2>
            <p className="mt-2 text-sm text-muted-foreground">Start free. Scale when you need to.</p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={[
                  "flex flex-col rounded-md border p-8 transition-shadow",
                  plan.highlighted
                    ? "border-primary bg-primary/5 shadow-[0_0_0_1px_hsl(var(--primary)/0.3)]"
                    : "border-border/20 bg-card",
                ].join(" ")}
              >
                {/* Name + tag */}
                <div className="flex items-center gap-2.5">
                  <span className="text-lg font-bold text-foreground">{plan.name}</span>
                  {plan.tag && (
                    <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                      {plan.tag}
                    </span>
                  )}
                </div>

                {/* Price */}
                <div className="mt-3 flex items-baseline gap-1">
                  <span className={["font-bold", plan.price.length <= 3 ? "text-4xl" : "text-2xl", plan.highlighted ? "text-primary" : "text-foreground"].join(" ")}>
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className="text-sm text-muted-foreground">{plan.period}</span>
                  )}
                </div>

                <p className="mt-2 text-sm text-muted-foreground">{plan.desc}</p>

                <hr className="my-6 border-border/20" />

                {/* Features */}
                <ul className="flex flex-1 flex-col gap-3">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-foreground">
                      <Dot />
                      {f}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                {plan.waitlistTier ? (
                  <button
                    onClick={() => setWaitlistTier(plan.waitlistTier)}
                    className={[
                      "mt-8 block w-full rounded py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      plan.highlighted
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "border border-border text-foreground hover:bg-accent",
                    ].join(" ")}
                  >
                    {plan.cta}
                  </button>
                ) : (
                  <a
                    href={plan.ctaHref!}
                    className={[
                      "mt-8 block rounded py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      plan.highlighted
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "border border-border text-foreground hover:bg-accent",
                    ].join(" ")}
                  >
                    {plan.cta}
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <hr className="border-border/20" />

      {/* ── Footer ────────────────────────────────────────── */}
      <footer className="px-16 py-12">
        <div className="mx-auto grid max-w-[1280px] gap-10 md:grid-cols-[1fr_auto_auto_auto]">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 text-primary">
              <TreadstoneSymbol className="size-5" />
              <p className="text-sm font-semibold tracking-wide">Treadstone</p>
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground/70">Agent-native sandbox platform.</p>
            <p className="mt-1 text-xs text-muted-foreground/40">&copy; 2026 Treadstone. Apache-2.0 License.</p>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Resources
            </h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li><a href="#install-cli" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">Install CLI</a></li>
              <li><a href={RELEASES_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">GitHub Releases</a></li>
              <li><a href={PYPI_CLI_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">Python SDK</a></li>
              <li><Link to="/auth/sign-in" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">Sign In</Link></li>
            </ul>
          </div>

          {/* Community */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Community
            </h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li><a href={GITHUB_URL} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">GitHub</a></li>
              <li><a href={`${GITHUB_URL}/stargazers`} target="_blank" rel="noreferrer" className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">Star on GitHub</a></li>
            </ul>
          </div>

          {/* Support */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Support
            </h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <a href={`mailto:${SUPPORT_EMAIL}`} className="transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
                  {SUPPORT_EMAIL}
                </a>
              </li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  )
}
