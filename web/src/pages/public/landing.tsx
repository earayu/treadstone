import { Link } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"
import { TreadstoneSymbol } from "@/components/brand/logo"

const GITHUB_URL = "https://github.com/earayu/treadstone"
const RELEASES_URL = "https://github.com/earayu/treadstone/releases"
const PYPI_CLI_URL = "https://pypi.org/project/treadstone-cli/"
const SUPPORT_EMAIL = "support@treadstone-ai.dev"

const INSTALL_SH = "curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh"
const INSTALL_PS = "irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex"
const INSTALL_PIP = "pip install treadstone-cli"

const USAGE_LINES = [
  { comment: "# Authenticate", cmd: "treadstone auth login" },
  { comment: "# Create a sandbox", cmd: "treadstone sandboxes create --template aio-sandbox-tiny --name demo" },
  { comment: "# List your sandboxes", cmd: "treadstone sandboxes list" },
  { comment: "# Hand off to a human via browser", cmd: "treadstone sandboxes web enable <sandbox_id>" },
]

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "/month",
    desc: "Get started with lightweight sandboxes.",
    features: [
      "aio-sandbox-tiny (0.25\u00a0core, 512\u00a0Mi)",
      "Sandbox lifecycle via CLI, SDK & API",
      "Browser hand-off sessions",
      "Auth & API key management",
      "Community support",
    ],
    cta: "Get Started",
    ctaHref: "/auth/sign-up",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "Usage-based",
    period: "",
    tag: "COMING SOON",
    desc: "More compute, more concurrency, priority support.",
    features: [
      "All templates up to aio-sandbox-large",
      "Multiple concurrent sandboxes",
      "Persistent storage (5\u201320\u00a0Gi)",
      "Usage analytics & reporting",
      "Priority support",
    ],
    cta: "Join Waitlist",
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    desc: "Self-host or fully managed.\u00a0Your infrastructure.",
    features: [
      "All templates including aio-sandbox-xlarge",
      "Unlimited concurrency",
      "Self-host on your Kubernetes cluster",
      "RBAC & multi-tenancy",
      "Dedicated SLA & integrations",
    ],
    cta: "Contact Us",
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
    highlighted: false,
  },
]

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

function Dot() {
  return <span className="mt-[5px] inline-block size-[5px] shrink-0 rounded-full bg-primary" aria-hidden="true" />
}

export function LandingPage() {
  const { data: user, isLoading } = useCurrentUser()
  const isLoggedIn = !isLoading && !!user

  return (
    <div>
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
          <h2 className="text-xl font-bold text-foreground">Usage</h2>

          <pre className="overflow-x-auto rounded border border-border/20 bg-black/40 px-6 py-5 font-mono text-[12.5px] leading-7 text-foreground">
            <code>
              {USAGE_LINES.map((line, i) => (
                <span key={i}>
                  <span className="text-muted-foreground/50">{line.comment}</span>
                  {"\n"}
                  <span className="text-primary">$&nbsp;</span>
                  <span>{line.cmd}</span>
                  {i < USAGE_LINES.length - 1 ? "\n\n" : ""}
                </span>
              ))}
            </code>
          </pre>

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

          <div className="grid gap-5 md:grid-cols-3">
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
                <a
                  href={plan.ctaHref}
                  {...(plan.ctaHref.startsWith("mailto") ? {} : {})}
                  className={[
                    "mt-8 block rounded py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    plan.highlighted
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "border border-border text-foreground hover:bg-accent",
                  ].join(" ")}
                >
                  {plan.cta}
                </a>
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
