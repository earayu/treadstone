import { useState, useEffect, useRef } from "react"
import { Link } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"
import { useSubmitWaitlistApplication } from "@/api/admin"
import { TreadstoneSymbol } from "@/components/brand/logo"
import { CodeBlockFrame } from "@/components/code/code-block-frame"
import { CopyButton } from "@/components/code/copy-button"
import { INTEGRATION_SURFACE_CODE_FRAME_HEADERS } from "@/lib/integration-surface-code-frame-headers"

const GITHUB_URL = "https://github.com/earayu/treadstone"
const DISCORD_URL = "https://discord.gg/ygSP9tT5RB"
const TWITTER_X_URL = "https://x.com/treadstone_ai"
/** Sign-in then return to repo root (for Star CTA). */
const GITHUB_STAR_LOGIN_URL = `https://github.com/login?return_to=${encodeURIComponent(GITHUB_URL)}`
const RELEASES_URL = "https://github.com/earayu/treadstone/releases"
const PYPI_CLI_URL = "https://pypi.org/project/treadstone-cli/"
const SUPPORT_EMAIL = "support@treadstone-ai.dev"

const INSTALL_SH = "curl -fsSL https://treadstone-ai.dev/install.sh | sh"
const INSTALL_PS = "irm https://treadstone-ai.dev/install.ps1 | iex"
const INSTALL_PIP = "pip install treadstone-cli"

// ── Terminal animation data ──────────────────────────────────────────────────

type TermStep =
  | { type: "cmt"; text: string }
  /** Narration / “thinking” lines — revealed character by character. `tone` matches prior sky vs zinc styling. */
  | { type: "think"; text: string; pause?: number; speed?: number; tone?: "sky" | "zinc" }
  | { type: "cmd"; text: string; speed?: number }
  | { type: "out"; text: string; pause?: number }
  | { type: "sp" }

// cmd / think `speed`: ms between keystrokes — lower is faster (not WPM).
const TERM_STEPS: TermStep[] = [
  { type: "think", text: "> request: check the target page (https://treadstone-ai.dev/) and see what’s going on", tone: "zinc", speed: 36 },
  { type: "think", text: "thinking: install the treadstone-cli skill for control-plane actions", pause: 180, tone: "sky", speed: 36 },
  { type: "cmd", text: "treadstone skills install --target project", speed: 34 },
  { type: "out", text: "✓ installed: .agents/skills/treadstone-cli/SKILL.md", pause: 240 },
  { type: "sp" },

  { type: "think", text: "thinking: this task needs a real browser and isolated runtime", tone: "zinc", speed: 36 },
  { type: "sp" },

  { type: "think", text: "thinking: confirm identity", tone: "zinc", speed: 36 },
  { type: "cmd", text: "treadstone auth whoami", speed: 34 },
  { type: "out", text: "✓ logged in as agent@example.com", pause: 220 },
  { type: "sp" },

  { type: "think", text: "thinking: create a sandbox", tone: "zinc", speed: 36 },
  { type: "cmd", text: "treadstone --json sandboxes create --template aio-sandbox-tiny --name page-check", speed: 38 },
  {
    type: "out",
    text: '{"id":"sb_3kx9m2p","status":"running","urls":{"proxy":"https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy","web":"https://sandbox-sb_3kx9m2p.treadstone-ai.dev/…"}}',
    pause: 380,
  },
  { type: "sp" },

  { type: "think", text: "thinking: prepare a browser session in case human review is needed", tone: "zinc", speed: 36 },
  { type: "cmd", text: "treadstone --json sandboxes web enable sb_3kx9m2p", speed: 38 },
  {
    type: "out",
    text: '{"open_link":"https://sandbox-sb_3kx9m2p.treadstone-ai.dev/_treadstone/open?token=...","expires_at":"2026-03-30T18:00:00Z"}',
    pause: 350,
  },
  { type: "sp" },

  { type: "think", text: "thinking: handoff is ready, stop the runtime", tone: "zinc", speed: 36 },
  { type: "cmd", text: "treadstone sandboxes stop sb_3kx9m2p", speed: 34 },
  { type: "out", text: "✓ sandbox stopped", pause: 270 },
  { type: "sp" },

  { type: "out", text: "✓ browser session ready for review", pause: 160 },
  { type: "out", text: "awaiting next instruction", pause: 260 },
]

// ── How It Works data ────────────────────────────────────────────────────────

const HOW_STEPS = [
  {
    n: "01 — ORCHESTRATE",
    title: "Agents control the workflow",
    desc: "Plan tasks, drive the CLI or API, and decide when to create, reuse, or stop a sandbox.",
  },
  {
    n: "02 — PROVISION",
    title: "Spin up a real environment",
    desc: "Each sandbox returns a urls object with proxy (HTTP into the workload), MCP, and web—not a single stateless call.",
  },
  {
    n: "03 — EXECUTE",
    title: "Run code, browse, and use tools",
    desc: "Send traffic through urls.proxy or MCP, or work on the filesystem—long-running work stays inside the sandbox.",
  },
  {
    n: "04 — HAND OFF",
    title: "Bring in a human only when needed",
    desc: "Issue a short-lived browser hand-off when an agent needs review, input, or a final decision.",
  },
]

// ── Plans data ───────────────────────────────────────────────────────────────

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "/month",
    badge: "ALWAYS FREE",
    badgeSoon: false,
    desc: "Get started with lightweight sandboxes.",
    features: [
      "10\u00a0CU-h compute / month",
      "1 concurrent sandbox",
      "aio-sandbox-tiny (0.25\u00a0core, 1\u00a0GiB)",
      "2\u00a0hr max auto-stop interval",
      "Sandbox lifecycle via CLI, SDK & API",
      "Browser hand-off sessions",
      "Community support",
    ],
    cta: "Get Started Free",
    ctaHref: "/auth/sign-up",
    highlighted: false,
    waitlistTier: null as string | null,
  },
  {
    name: "Pro",
    price: "Usage-based",
    period: "",
    badge: "COMING SOON",
    badgeSoon: true,
    desc: "More compute, more concurrency, priority support.",
    features: [
      "80\u00a0CU-h compute / month",
      "3 concurrent sandboxes",
      "All templates up to aio-sandbox-medium",
      "10\u00a0GiB persistent storage",
      "8\u00a0hr max auto-stop interval",
      "Usage analytics & reporting",
      "Priority support",
    ],
    cta: "Apply for Early Access",
    ctaHref: null,
    highlighted: true,
    waitlistTier: "pro",
  },
  {
    name: "Ultra",
    price: "Usage-based",
    period: "",
    badge: "COMING SOON",
    badgeSoon: true,
    desc: "Maximum compute and concurrency for heavy workloads.",
    features: [
      "240\u00a0CU-h compute / month",
      "5 concurrent sandboxes",
      "All templates up to aio-sandbox-medium",
      "30\u00a0GiB persistent storage",
      "24\u00a0hr max auto-stop interval",
      "Dedicated SLA & integrations",
    ],
    cta: "Apply for Early Access",
    ctaHref: null,
    highlighted: false,
    waitlistTier: "ultra",
  },
  {
    name: "Custom",
    price: "Custom",
    period: "",
    badge: "ENTERPRISE",
    badgeSoon: false,
    desc: "Negotiated limits for teams and long-running workloads.",
    features: [
      "800\u00a0CU-h compute / month",
      "10 concurrent sandboxes",
      "100\u00a0GiB persistent storage",
      "72\u00a0hr max auto-stop interval",
      "12\u00a0hr grace period",
      "All sandbox templates",
      "Contact us for terms & SLA",
    ],
    cta: "Contact Us",
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
    highlighted: false,
    waitlistTier: null as string | null,
  },
]

// ── Code tab content (syntax-highlighted via spans) ──────────────────────────

import { CodeLines, cm, pr, fg, ok, js, kw, fn, type CodeLine } from "@/components/code/code-lines"
const CLI_LINES: CodeLine[] = [
  [{ cls: cm, text: "# 1. Authenticate (or set TREADSTONE_API_KEY in env)" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone auth login --email agent@example.com --password ••••••••" }],
  [{ cls: ok, text: "✓ Logged in as agent@example.com" }],
  [],
  [{ cls: cm, text: "# 2. Install the agent skill (Cursor, Codex, …)" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone skills install" }],
  [{ cls: ok, text: "Installed: ~/.agents/skills/treadstone-cli/SKILL.md" }],
  [],
  [{ cls: cm, text: "# 3. See available templates" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone --json templates list" }],
  [{ cls: js, text: '{"items": [{"name": "aio-sandbox-tiny", "cpu": "0.25", "memory": "512Mi"}, ...]}' }],
  [],
  [{ cls: cm, text: "# 4. Create a sandbox — read id and urls from JSON" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone --json sandboxes create --template aio-sandbox-tiny --name agent-demo" }],
  [
    {
      cls: js,
      text: '{"id": "sb_3kx9m2p", "status": "running", "urls": {"proxy": "https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy", "web": "https://sandbox-sb_3kx9m2p.treadstone-ai.dev/…"}}',
    },
  ],
  [],
  [{ cls: cm, text: "# 5. Hand the browser off to a human" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone --json sandboxes web enable sb_3kx9m2p" }],
  [
    {
      cls: js,
      text: '{"open_link": "https://sandbox-sb_3kx9m2p.treadstone-ai.dev/_treadstone/open?token=...", "expires_at": "2026-03-30T18:00:00Z"}',
    },
  ],
]

const SDK_LINES: CodeLine[] = [
  [{ cls: kw, text: "from " }, { cls: fg, text: "treadstone_sdk " }, { cls: kw, text: "import " }, { cls: fg, text: "AuthenticatedClient" }],
  [{ cls: kw, text: "from " }, { cls: fg, text: "treadstone_sdk.api.sandboxes " }, { cls: kw, text: "import " }, { cls: fg, text: "sandboxes_create_sandbox, sandboxes_create_sandbox_web_link" }],
  [{ cls: kw, text: "from " }, { cls: fg, text: "treadstone_sdk.models.create_sandbox_request " }, { cls: kw, text: "import " }, { cls: fg, text: "CreateSandboxRequest" }],
  [],
  [{ cls: fg, text: "client = AuthenticatedClient(" }],
  [{ cls: fg, text: '    base_url=' }, { cls: ok, text: '"https://api.treadstone-ai.dev"' }, { cls: fg, text: "," }],
  [{ cls: fg, text: '    token=' }, { cls: ok, text: '"sk-..."' }],
  [{ cls: fg, text: ")" }],
  [],
  [{ cls: cm, text: "# Create a sandbox" }],
  [{ cls: fg, text: "sandbox = sandboxes_create_sandbox." }, { cls: fn, text: "sync" }, { cls: fg, text: "(" }],
  [{ cls: fg, text: "    client=client," }],
  [{ cls: fg, text: "    body=CreateSandboxRequest(" }],
  [{ cls: fg, text: '        template=' }, { cls: ok, text: '"aio-sandbox-tiny"' }, { cls: fg, text: "," }],
  [{ cls: fg, text: '        name=' }, { cls: ok, text: '"agent-demo"' }],
  [{ cls: fg, text: "    )" }],
  [{ cls: fg, text: ")" }],
  [{ cls: fn, text: "print" }, { cls: fg, text: "(sandbox.id)            " }, { cls: cm, text: '# "sb_3kx9m2p"' }],
  [
    { cls: fn, text: "print" },
    { cls: fg, text: "(sandbox.urls.proxy)    " },
    { cls: cm, text: '# "https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy"' },
  ],
  [],
  [{ cls: cm, text: "# Generate a browser hand-off URL for a human" }],
  [{ cls: fg, text: "session = sandboxes_create_sandbox_web_link." }, { cls: fn, text: "sync" }, { cls: fg, text: "(sandbox.id, client=client)" }],
  [
    { cls: fn, text: "print" },
    { cls: fg, text: "(session.open_link)     " },
    {
      cls: cm,
      text: '# "https://sandbox-sb_3kx9m2p.treadstone-ai.dev/_treadstone/open?token=..."',
    },
  ],
]

const REST_LINES: CodeLine[] = [
  [{ cls: cm, text: "# Create a sandbox" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "curl -X POST https://api.treadstone-ai.dev/v1/sandboxes \\" }],
  [{ cls: fg, text: "    -H " }, { cls: ok, text: '"Authorization: Bearer $TREADSTONE_API_KEY"' }, { cls: fg, text: " \\" }],
  [{ cls: fg, text: "    -H " }, { cls: ok, text: '"Content-Type: application/json"' }, { cls: fg, text: " \\" }],
  [{ cls: fg, text: "    -d " }, { cls: ok, text: `'{"name": "agent-demo", "template": "aio-sandbox-tiny"}'` }],
  [],
  [{ cls: js, text: "{" }],
  [{ cls: js, text: '  "id": "sb_3kx9m2p",' }],
  [{ cls: js, text: '  "name": "agent-demo",' }],
  [{ cls: js, text: '  "status": "running",' }],
  [{ cls: js, text: '  "urls": {' }],
  [
    {
      cls: js,
      text: '    "proxy": "https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy",',
    },
  ],
  [
    {
      cls: js,
      text: '    "web": "https://sandbox-sb_3kx9m2p.treadstone-ai.dev/…"',
    },
  ],
  [{ cls: js, text: "  }" }],
  [{ cls: js, text: "}" }],
  [],
  [{ cls: cm, text: "# Enable browser hand-off for a human" }],
  [{ cls: pr, text: "$ " }, { cls: fg, text: "curl -X POST https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/web-link \\" }],
  [{ cls: fg, text: "    -H " }, { cls: ok, text: '"Authorization: Bearer $TREADSTONE_API_KEY"' }],
  [],
  [{ cls: js, text: "{" }],
  [
    {
      cls: js,
      text: '  "open_link": "https://sandbox-sb_3kx9m2p.treadstone-ai.dev/_treadstone/open?token=...",',
    },
  ],
  [{ cls: js, text: '  "expires_at": "2026-03-30T18:00:00Z"' }],
  [{ cls: js, text: "}" }],
]

function CliCode() {
  return <CodeLines lines={CLI_LINES} />
}

function SdkCode() {
  return <CodeLines lines={SDK_LINES} />
}

function RestCode() {
  return <CodeLines lines={REST_LINES} />
}

// ── Sub-components ────────────────────────────────────────────────────────────

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
        use_case: useCase || undefined,  // empty string becomes undefined for non-required tiers
      },
      {
        onSuccess: () => setSubmitted(true),
        onError: (err) => setError(err.message),
      },
    )
  }

  const tierLabel = tier === "pro" ? "Pro" : "Ultra"
  const useCaseRequired = tier === "ultra"

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md rounded-md border border-border/30 bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/20 px-5 py-4">
          <div>
            <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
              APPLY FOR FREE ACCESS —{" "}
            </span>
            <span className="text-[11px] font-bold uppercase tracking-[1.5px] text-primary">{tierLabel}</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground transition-colors hover:text-foreground">
            ✕
          </button>
        </div>

        {submitted ? (
          <div className="px-5 py-10 text-center">
            <p className="text-lg font-semibold text-primary">Application submitted!</p>
            <p className="mt-2 text-sm text-muted-foreground">
              We'll review your application and upgrade your account to the {tierLabel} plan shortly. Make sure you've
              signed up at{" "}
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
              We're granting free {tierLabel} access during our early launch. Fill in your details and we'll upgrade
              your account.
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
                How do you plan to use it?{" "}
                {useCaseRequired ? (
                  <span className="text-destructive">*</span>
                ) : (
                  <span className="text-muted-foreground/50">(optional)</span>
                )}
              </label>
              <textarea
                required={useCaseRequired}
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                placeholder="e.g. Building AI coding agents that need isolated execution environments"
                rows={3}
                maxLength={1000}
                className="resize-none rounded-sm border border-border/40 bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

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

function InstallCard({ os, hint, cmd, first }: { os: string; hint: string; cmd: string; first: boolean }) {
  const [copied, setCopied] = useState(false)

  const triggerCopy = () => {
    navigator.clipboard.writeText(cmd).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div
      className={[
        "flex flex-col gap-4 rounded-xl border border-border/20 bg-white/[0.02] p-6 transition-colors hover:bg-white/[0.035]",
        !first ? "mt-3 md:mt-0 md:ml-3" : "",
      ].join(" ")}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[13.5px] font-semibold text-foreground">{os}</span>
          <span className="ml-2 font-mono text-[10.5px] text-muted-foreground/40">{hint}</span>
        </div>
        <CopyButton copied={copied} onCopy={triggerCopy} />
      </div>

      {/* Command block — click anywhere to copy */}
      <div
        role="button"
        tabIndex={0}
        title="Click to copy"
        onClick={triggerCopy}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && triggerCopy()}
        className={[
          "flex-1 cursor-pointer select-none rounded-lg border px-4 py-3.5 transition-all",
          copied
            ? "border-primary/30 bg-primary/[0.06]"
            : "border-border/[0.15] bg-black/30 hover:border-border/30 hover:bg-black/40",
        ].join(" ")}
      >
        <code className="block break-all font-mono text-[12px] leading-[1.7] text-foreground/80">{cmd}</code>
      </div>
    </div>
  )
}

// ── Animated terminal ─────────────────────────────────────────────────────────

type RenderedLine =
  | { kind: "cmt"; text: string }
  | { kind: "think"; text: string; tone: "sky" | "zinc" }
  | { kind: "cmd"; prompt: string; text: string }
  | { kind: "out"; text: string }
  | { kind: "sp" }

function AnimatedTerminal() {
  const [lines, setLines] = useState<RenderedLine[]>([])
  const [cursor, setCursor] = useState(true)
  const animating = useRef(false)

  useEffect(() => {
    if (animating.current) return
    animating.current = true

    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

    async function run() {
      await sleep(950)
      for (const step of TERM_STEPS) {
        if (step.type === "sp") {
          setLines((prev) => [...prev, { kind: "sp" }])
          continue
        }
        if (step.type === "cmt") {
          setLines((prev) => [...prev, { kind: "cmt", text: step.text }])
          await sleep(150)
          continue
        }
        if (step.type === "think") {
          const tone = step.tone ?? "zinc"
          const speed = step.speed ?? 40
          await sleep(step.pause ?? 0)
          setLines((prev) => [...prev, { kind: "think", text: "", tone }])
          await sleep(80)
          for (const ch of step.text) {
            setLines((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last?.kind === "think") {
                next[next.length - 1] = { kind: "think", text: last.text + ch, tone }
              }
              return next
            })
            await sleep(speed + Math.random() * speed * 0.25)
          }
          await sleep(120)
          continue
        }
        if (step.type === "cmd") {
          const speed = step.speed ?? 40
          setLines((prev) => [...prev, { kind: "cmd", prompt: "$ ", text: "" }])
          await sleep(150)
          for (const ch of step.text) {
            setLines((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last.kind === "cmd") {
                next[next.length - 1] = { ...last, text: last.text + ch }
              }
              return next
            })
            await sleep(speed + Math.random() * speed * 0.25)
          }
          await sleep(180)
          continue
        }
        if (step.type === "out") {
          await sleep(step.pause ?? 280)
          setLines((prev) => [...prev, { kind: "out", text: step.text }])
          await sleep(130)
        }
      }
      setCursor(false)
    }

    run()
  }, [])

  return (
    <div className="w-[740px] max-w-full overflow-hidden rounded-xl border border-border/20 bg-black/40 text-left">
      {/* Window chrome */}
      <div className="flex items-center gap-1.5 border-b border-border/20 bg-white/[0.03] px-4 py-3">
        <span className="size-3 rounded-full bg-[#ff5f56]" />
        <span className="size-3 rounded-full bg-[#ffbd2e]" />
        <span className="size-3 rounded-full bg-[#27c93f]" />
        <span className="ml-2 font-mono text-[10.5px] text-muted-foreground/30">bash — treadstone getting started</span>
      </div>
      {/* Body */}
      <div className="min-h-[260px] px-5 py-5 font-mono text-[12.5px] leading-[1.75]">
        {lines.map((line, i) => {
          if (line.kind === "sp") return <div key={i} className="h-[10px]" />
          if (line.kind === "cmt")
            return (
              <div key={i} className="text-zinc-400">
                {line.text}
              </div>
            )
          if (line.kind === "think")
            return (
              <div
                key={i}
                className={line.tone === "sky" ? "text-sky-300/80" : "text-zinc-400"}
              >
                {line.text}
              </div>
            )
          if (line.kind === "cmd")
            return (
              <div key={i}>
                <span className="text-primary">{line.prompt}</span>
                <span className="text-foreground">{line.text}</span>
              </div>
            )
          return (
            <div key={i} className="text-sky-300/80">
              {line.text}
            </div>
          )
        })}
        {cursor && (
          <span className="inline-block h-[14px] w-[7px] animate-[blink_1s_step-end_infinite] bg-primary align-text-bottom" />
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function LandingPage() {
  const { data: user, isLoading } = useCurrentUser()
  const isLoggedIn = !isLoading && !!user
  const [waitlistTier, setWaitlistTier] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"cli" | "sdk" | "rest">("cli")

  const cliCode = [
    "# 1. Authenticate (or set TREADSTONE_API_KEY in env)",
    "$ treadstone auth login --email agent@example.com --password ••••••••",
    "✓ Logged in as agent@example.com",
    "",
    "# 2. Install the agent skill (Cursor, Codex, …)",
    "$ treadstone skills install",
    "Installed: ~/.agents/skills/treadstone-cli/SKILL.md",
    "",
    "# 3. See available templates",
    "$ treadstone --json templates list",
    '{"items": [{"name": "aio-sandbox-tiny", "cpu": "0.25", "memory": "512Mi"}, ...]}',
    "",
    "# 4. Create a sandbox — read id and urls from JSON",
    "$ treadstone --json sandboxes create --template aio-sandbox-tiny --name agent-demo",
    '{"id":"sb_3kx9m2p","status":"running","urls":{"proxy":"https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy","web":"https://sandbox-sb_3kx9m2p.treadstone-ai.dev/…"}}',
    "",
    "# 5. Hand the browser off to a human",
    "$ treadstone --json sandboxes web enable sb_3kx9m2p",
    '{"open_link":"https://sandbox-sb_3kx9m2p.treadstone-ai.dev/_treadstone/open?token=...","expires_at":"2026-03-30T18:00:00Z"}',
  ].join("\n")
  const sdkCode =
    'from treadstone_sdk import AuthenticatedClient\nfrom treadstone_sdk.api.sandboxes import sandboxes_create_sandbox, sandboxes_create_sandbox_web_link\nfrom treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest\n\nclient = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="sk-...")\nsandbox = sandboxes_create_sandbox.sync(client=client, body=CreateSandboxRequest(template="aio-sandbox-tiny", name="agent-demo"))\nprint(sandbox.urls.proxy)  # https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/proxy\nsession = sandboxes_create_sandbox_web_link.sync(sandbox.id, client=client)\nprint(session.open_link)'
  const restCode = [
    "curl -X POST https://api.treadstone-ai.dev/v1/sandboxes \\",
    '  -H "Authorization: Bearer $TREADSTONE_API_KEY" \\',
    '  -H "Content-Type: application/json" \\',
    "  -d '{\"name\": \"agent-demo\", \"template\": \"aio-sandbox-tiny\"}'",
    "",
    "# … then enable browser hand-off",
    "curl -X POST https://api.treadstone-ai.dev/v1/sandboxes/sb_3kx9m2p/web-link \\",
    '  -H "Authorization: Bearer $TREADSTONE_API_KEY"',
  ].join("\n")

  const tabCopyText = { cli: cliCode, sdk: sdkCode, rest: restCode }

  return (
    <div>
      {waitlistTier && <WaitlistDialog tier={waitlistTier} onClose={() => setWaitlistTier(null)} />}

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="relative flex min-h-[calc(100vh-56px)] flex-col items-center justify-center overflow-hidden px-8 pb-20 pt-24 text-center">
        {/* Glow */}
        <div
          className="pointer-events-none absolute left-1/2 top-0 -z-0 h-[600px] w-[700px] -translate-x-1/2 -translate-y-1/4"
          style={{ background: "radial-gradient(ellipse, rgba(29,255,138,0.06) 0%, transparent 65%)" }}
        />

        <div className="relative z-10 flex w-full flex-col items-center">
          {/* Badge */}
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/[0.08] px-4 py-1.5">
            <span className="size-[6px] animate-pulse rounded-full bg-primary" />
            <span className="font-mono text-[11px] font-medium tracking-[0.04em] text-primary">
              Agent-native sandbox infrastructure
            </span>
          </div>

          <h1 className="text-balance font-mono text-[clamp(2.25rem,4.8vw,3.75rem)] font-semibold leading-[1.08] tracking-[-0.04em]">
            Sandboxes for agents
            <br />
            <span className="text-primary">that don't wait for humans.</span>
          </h1>

          <div className="mt-5 mx-auto w-full max-w-[min(36rem,100%)] space-y-3 text-center">
            <p className="text-[17px] leading-[1.65] text-muted-foreground">
              Isolated sandboxes for coding, browsing, 
              <br />
              testing, and long-running tasks.
            </p>
            <p className="text-[17px] leading-[1.65] text-muted-foreground">
              Built so agents can drive Treadstone from the CLI, SDK, or API—
              <br />
              launching and managing sandboxes on their own.
            </p>
          </div>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            {isLoggedIn ? (
              <Link
                to="/app"
                className="rounded-[10px] bg-primary px-7 py-3.5 text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Open Console
              </Link>
            ) : (
              <Link
                to="/auth/sign-up"
                className="rounded-[10px] bg-primary px-7 py-3.5 text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Get Started Free
              </Link>
            )}
            <button
              type="button"
              onClick={() => {
                setWaitlistTier("pro")
                document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth", block: "start" })
                window.history.replaceState(null, "", "#pricing")
              }}
              className="rounded-[10px] border border-border/30 px-7 py-3.5 text-[15px] font-semibold text-muted-foreground transition-colors hover:border-border/50 hover:bg-white/[0.04] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Apply for Early Access
            </button>
          </div>

          <div className="mt-14 w-full max-w-[740px]">
            <AnimatedTerminal />
          </div>
        </div>
      </section>

      {/* ── How It Works ──────────────────────────────────────── */}
      <section className="mx-auto max-w-[1080px] px-10 py-24">
        <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// execution model</span>
        <h2 className="mt-3 font-mono text-[clamp(1.75rem,3.5vw,2.75rem)] font-semibold leading-[1.1] tracking-[-0.04em]">
          Built for autonomous agent workflows.
        </h2>
        <p className="mt-3 mb-12 max-w-[520px] text-base leading-[1.65] text-muted-foreground">
          One control plane for lifecycle and keys; each sandbox exposes <span className="font-mono text-[13px] text-foreground/80">urls</span> for
          proxy, MCP, and browser access. Agents run work in the sandbox and hand off to humans when needed.
        </p>

        <div className="grid grid-cols-1 overflow-hidden rounded-xl border border-border/20 sm:grid-cols-2 lg:grid-cols-4">
          {HOW_STEPS.map((step, i) => (
            <div
              key={step.n}
              className={[
                "bg-background p-7",
                i < HOW_STEPS.length - 1 ? "border-b lg:border-b-0 lg:border-r" : "",
                "border-border/20",
              ].join(" ")}
            >
              <span className="font-mono text-[10px] tracking-[0.1em] text-muted-foreground/40">{step.n}</span>
              <div className="mt-3.5 text-[14px] font-semibold">{step.title}</div>
              <p className="mt-2 text-[12.5px] leading-[1.6] text-muted-foreground">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Code Tabs ─────────────────────────────────────────── */}
      <div id="integrate" className="border-y border-border/20 bg-white/[0.015] px-10 py-24">
        <div className="mx-auto max-w-[1080px]">
          <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// integrate</span>
          <h2 className="mt-3 font-mono text-[clamp(1.75rem,3.5vw,2.75rem)] font-semibold leading-[1.1] tracking-[-0.04em]">
            Three ways in.
          </h2>
          <p className="mt-3 mb-6 max-w-[560px] text-base leading-[1.65] text-muted-foreground">
            CLI, Python SDK, or raw HTTP against the same control plane. Use{" "}
            <code className="rounded-sm bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px]">--json</code> for stable CLI
            output; sandbox detail includes <span className="font-mono text-[13px] text-foreground/80">urls</span> for the
            data plane (
            <Link to="/docs/sandbox-endpoints" className="text-primary underline underline-offset-2 hover:text-primary/90">
              Sandbox endpoints
            </Link>
            ).
          </p>

          {/* Tab bar */}
          <div className="mb-6 flex w-fit overflow-hidden rounded-lg border border-border/20">
            {(
              [
                { id: "cli", label: "CLI", color: "bg-primary" },
                { id: "sdk", label: "Python SDK", color: "bg-sky-400" },
                { id: "rest", label: "REST API", color: "bg-purple-400" },
              ] as const
            ).map((tab, i, arr) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={[
                  "flex items-center gap-2 px-5 py-2.5 font-mono text-[12.5px] font-medium transition-colors",
                  i < arr.length - 1 ? "border-r border-border/20" : "",
                  activeTab === tab.id
                    ? "bg-white/[0.06] text-foreground"
                    : "text-muted-foreground hover:bg-white/[0.03]",
                ].join(" ")}
              >
                <span className={`size-[7px] rounded-full ${tab.color}`} />
                {tab.label}
              </button>
            ))}
          </div>

          <CodeBlockFrame
            headerLabel={INTEGRATION_SURFACE_CODE_FRAME_HEADERS[activeTab]}
            headerRight={<CopyButton text={tabCopyText[activeTab]} />}
          >
            {activeTab === "cli" && <CliCode />}
            {activeTab === "sdk" && <SdkCode />}
            {activeTab === "rest" && <RestCode />}
          </CodeBlockFrame>
        </div>
      </div>

      {/* ── Install ───────────────────────────────────────────── */}
      <div id="install" className="border-y border-border/20 bg-white/[0.015] px-10 py-24">
        <div className="mx-auto max-w-[1080px]">
          <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// install</span>
          <h2 className="mt-3 font-mono text-[clamp(1.75rem,3.5vw,2.75rem)] font-semibold leading-[1.1] tracking-[-0.04em]">
            Up in seconds.
          </h2>
          <p className="mt-3 mb-12 max-w-[560px] text-base leading-[1.65] text-muted-foreground">
            Install the CLI with curl, PowerShell, or pip—the same commands as the{" "}
            <Link to="/docs/quickstart" className="text-primary underline underline-offset-2 hover:text-primary/90">
              Quickstart
            </Link>
            . Then run{" "}
            <code className="rounded-sm bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px]">treadstone auth login</code> and
            create an API key when you automate. The Python SDK and REST API only need{" "}
            <code className="rounded-sm bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px]">TREADSTONE_API_KEY</code>.
          </p>

          <div className="mb-8 grid grid-cols-1 md:grid-cols-3 md:items-stretch">
            {[
              { os: "macOS / Linux", hint: "curl installer", cmd: INSTALL_SH },
              { os: "Windows", hint: "PowerShell", cmd: INSTALL_PS },
              { os: "pip", hint: "Python package", cmd: INSTALL_PIP },
            ].map((card, i) => (
              <InstallCard key={card.os} os={card.os} hint={card.hint} cmd={card.cmd} first={i === 0} />
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex gap-5">
              {[
                { label: "GitHub →", href: GITHUB_URL, external: true },
                { label: "Discord →", href: DISCORD_URL, external: true },
                { label: "X →", href: TWITTER_X_URL, external: true },
                { label: "Releases →", href: RELEASES_URL, external: true },
                { label: "PyPI →", href: PYPI_CLI_URL, external: true },
              ].map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[13px] text-muted-foreground transition-colors hover:text-primary"
                >
                  {link.label}
                </a>
              ))}
            </div>
            <span className="text-[12.5px] text-muted-foreground/50">
              Also available:{" "}
              <a href={PYPI_CLI_URL} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-foreground">
                pip install treadstone-sdk
              </a>
            </span>
          </div>
        </div>
      </div>

      {/* ── Plans ─────────────────────────────────────────────── */}
      <section id="pricing" className="mx-auto max-w-[1080px] scroll-mt-20 px-10 py-24">
        <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// pricing</span>
        <h2 className="mt-3 font-mono text-[clamp(1.75rem,3.5vw,2.75rem)] font-semibold leading-[1.1] tracking-[-0.04em]">
          Start free.
          <br />
          Scale when you need to.
        </h2>
        <p className="mt-3 mb-12 max-w-[480px] text-base leading-[1.65] text-muted-foreground">
          All plans include the CLI, Python SDK, and REST API. Compute is measured in CU-hours.
        </p>

        <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={[
                "flex flex-col rounded-xl border p-6 transition-colors",
                plan.highlighted
                  ? "border-primary/30 bg-primary/[0.04] hover:border-primary/50"
                  : "border-border/20 bg-white/[0.02] hover:border-border/40",
              ].join(" ")}
            >
              <div className="text-[15px] font-semibold tracking-[-0.01em]">{plan.name}</div>
              <span
                className={[
                  "mt-1.5 w-fit rounded px-2 py-0.5 font-mono text-[9.5px] font-semibold tracking-[0.08em]",
                  plan.badgeSoon
                    ? "bg-primary/[0.08] text-primary"
                    : "bg-white/[0.07] text-muted-foreground",
                ].join(" ")}
              >
                {plan.badge}
              </span>

              <div
                className={[
                  "mt-4 font-mono font-semibold leading-none tracking-[-0.05em]",
                  plan.price.length <= 3 ? "text-[34px]" : "text-[22px]",
                  plan.highlighted ? "text-primary" : "text-foreground",
                ].join(" ")}
              >
                {plan.price}
              </div>
              <div className="mt-1 text-[12px] text-muted-foreground">
                {plan.period || "pay per CU-hour used"}
              </div>

              <hr className="my-5 border-border/20" />

              <ul className="flex flex-1 flex-col gap-1.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-[12.5px] leading-[1.45] text-muted-foreground">
                    <span className="mt-[3px] shrink-0 font-bold text-primary">·</span>
                    {f}
                  </li>
                ))}
              </ul>

              <div className="mt-5">
                {plan.waitlistTier ? (
                  <button
                    onClick={() => setWaitlistTier(plan.waitlistTier)}
                    className={[
                      "block w-full rounded-lg py-2.5 text-center text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      plan.highlighted
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "border border-border/30 text-foreground hover:bg-white/[0.04]",
                    ].join(" ")}
                  >
                    {plan.cta}
                  </button>
                ) : (
                  <a
                    href={plan.ctaHref!}
                    className={[
                      "block rounded-lg py-2.5 text-center text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      plan.highlighted
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "border border-border/30 text-foreground hover:bg-white/[0.04]",
                    ].join(" ")}
                  >
                    {plan.cta}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      <hr className="border-border/20" />

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="px-10 pb-8 pt-12">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-start justify-between gap-12">
          <div>
            <div className="flex items-center gap-2.5 font-mono text-[14px] font-semibold text-foreground">
              <TreadstoneSymbol className="size-[22px] shrink-0 text-primary" />
              treadstone
            </div>
            <p className="mt-3 max-w-[220px] text-[12.5px] leading-[1.6] text-muted-foreground/50">
              Agent-native sandbox platform. Run code, build software, and hand off browser sessions from isolated
              environments.
            </p>
          </div>

          <div className="flex gap-14 flex-shrink-0">
            <div>
              <span className="font-mono text-[10px] tracking-[0.1em] text-muted-foreground/40">RESOURCES</span>
              <ul className="mt-3.5 flex flex-col gap-2.5">
                {[
                  { label: "Docs Overview", href: "/docs" },
                  { label: "Quickstart", href: "/docs/quickstart" },
                  { label: "CLI Guide", href: "/docs/cli-guide" },
                  { label: "REST API Guide", href: "/docs/rest-api-guide" },
                  { label: "Python SDK Guide", href: "/docs/python-sdk-guide" },
                  { label: "REST API Reference", href: "/docs/api-reference" },
                  { label: "CLI on PyPI", href: PYPI_CLI_URL, external: true },
                  { label: "GitHub Releases", href: RELEASES_URL, external: true },
                ].map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      target={l.external ? "_blank" : undefined}
                      rel={l.external ? "noreferrer" : undefined}
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <span className="font-mono text-[10px] tracking-[0.1em] text-muted-foreground/40">COMMUNITY</span>
              <ul className="mt-3.5 flex flex-col gap-2.5">
                {[
                  { label: "Star on GitHub ★", href: GITHUB_STAR_LOGIN_URL },
                  { label: "Discord", href: DISCORD_URL },
                  { label: "X (Twitter)", href: TWITTER_X_URL },
                ].map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <span className="font-mono text-[10px] tracking-[0.1em] text-muted-foreground/40">SUPPORT</span>
              <ul className="mt-3.5 flex flex-col gap-2.5">
                <li>
                  <a
                    href={`mailto:${SUPPORT_EMAIL}`}
                    className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {SUPPORT_EMAIL}
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mx-auto mt-10 flex max-w-[1080px] items-center justify-between border-t border-border/20 pt-5">
          <span className="text-[11.5px] text-muted-foreground/40">© 2026 Treadstone. Apache-2.0 License.</span>
          <span className="text-[11.5px] text-muted-foreground/40">Agent-native sandbox platform.</span>
        </div>
      </footer>
    </div>
  )
}
