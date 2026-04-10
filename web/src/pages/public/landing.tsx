import { useState, useEffect, useRef } from "react"
import { Link } from "react-router"
import { useSubmitWaitlistApplication } from "@/api/admin"
import { TreadstoneSymbol } from "@/components/brand/logo"
import { CopyButton } from "@/components/code/copy-button"
import { LANDING_PAGE_TITLE, attachLandingJsonLd } from "@/lib/landing-seo"

const GITHUB_URL = "https://github.com/earayu/treadstone"
const DISCORD_URL = "https://discord.gg/ygSP9tT5RB"
const TWITTER_X_URL = "https://x.com/treadstone_ai"
/** Sign-in then return to repo root (for Star CTA). */
const GITHUB_STAR_LOGIN_URL = `https://github.com/login?return_to=${encodeURIComponent(GITHUB_URL)}`
const RELEASES_URL = "https://github.com/earayu/treadstone/releases"
const PYPI_CLI_URL = "https://pypi.org/project/treadstone-cli/"
const SUPPORT_EMAIL = "support@treadstone-ai.dev"

/** Hero primary CTA for visitors — opens the hosted public demo sandbox Web UI in a new tab. */
const PUBLIC_DEMO_SANDBOX_URL =
  "https://sandbox-sba1ad15f841c32f2f.treadstone-ai.dev/_treadstone/open?token=swld751d929b7f5efc0b11f426f"

/** Hero animated terminal: hidden by default; set to `true` to show it again (side-by-side on large screens). */
const SHOW_HERO_TERMINAL = false

const INSTALL_SH = "curl -fsSL https://treadstone-ai.dev/install.sh | sh"

/** Example sandbox id / JSON from a real `sandboxes create --name my-sandbox` run (token in urls.web masked). */
const EXAMPLE_SANDBOX_ID = "sb3a14984f563171eb"
const QUICKSTART_CREATE_OUTPUT = `{
  "id": "${EXAMPLE_SANDBOX_ID}",
  "name": "my-sandbox",
  "template": "aio-sandbox-tiny",
  "status": "ready",
  "labels": {},
  "auto_stop_interval": 15,
  "auto_delete_interval": -1,
  "persist": false,
  "storage_size": null,
  "urls": {
    "proxy": "https://app.treadstone-ai.dev/v1/sandboxes/${EXAMPLE_SANDBOX_ID}/proxy",
    "mcp": "https://app.treadstone-ai.dev/v1/sandboxes/${EXAMPLE_SANDBOX_ID}/proxy/mcp",
    "web": "https://sandbox-${EXAMPLE_SANDBOX_ID}.treadstone-ai.dev/_treadstone/open?token=…"
  },
  "created_at": "2026-04-09T07:12:36.423063Z"
}`

/**
 * Quickstart step 5 — shell/exec body (runs inside the sandbox).
 * Inner command: Algolia HN + jq — Ask HN uses `item?id=` when `url` is null.
 * The jq filter uses single quotes; use `-d @- <<'EOF'` so the JSON can contain `'` safely.
 * In this template literal, `\\` before `(` / `n` preserves jq’s `\\(.title)`, `\\n`, `\\((…`.
 */
const QUICKSTART_STEP5_SHELL_BODY = JSON.stringify({
  command: `curl -sS "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10" | jq -r '.hits[] | "\\(.title) (\\(.points) points) \\n\\((if .url then .url else "https://news.ycombinator.com/item?id=" + (.objectID|tostring) end))\\n"'`,
  exec_dir: "/tmp",
})

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

// ── Quickstart steps data ─────────────────────────────────────────────────────
// Each step uses `blocks`: one or more copy-paste shell blocks (TiDB-style), each with its own Copy control.

const QUICKSTART_STEPS = [
  {
    n: "01",
    title: "Install the CLI",
    desc: "Install the treadstone CLI on your machine.",
    blocks: [{ headerLabel: "macOS / Linux — curl installer", cmd: INSTALL_SH }],
    output: "✓ installed: treadstone CLI",
    outputNote: `pip install treadstone-cli  ·  Windows: irm https://treadstone-ai.dev/install.ps1 | iex`,
  },
  {
    n: "02",
    title: "Authenticate",
    desc: "Sign in so the CLI can talk to Treadstone.",
    blocks: [{ headerLabel: "bash", cmd: "treadstone auth login" }],
    output: "✓ Logged in as you@example.com",
    outputNote: "Headless / CI: create an API key in the console and export TREADSTONE_API_KEY.",
  },
  {
    n: "03",
    title: "Create a sandbox and export URLs",
    desc: "Create a sandbox, keep the JSON in a shell variable, and export TREADSTONE_* for the next steps—no file on disk.",
    blocks: [
      {
        headerLabel: "bash",
        cmd: `TREADSTONE_SANDBOX_JSON=$(treadstone --json sandboxes create --name my-sandbox)
export TREADSTONE_SANDBOX_ID=$(jq -r '.id' <<< "$TREADSTONE_SANDBOX_JSON")
export TREADSTONE_PROXY_URL=$(jq -r '.urls.proxy' <<< "$TREADSTONE_SANDBOX_JSON")
export TREADSTONE_WEB_URL=$(jq -r '.urls.web' <<< "$TREADSTONE_SANDBOX_JSON")
export TREADSTONE_MCP_URL=$(jq -r '.urls.mcp' <<< "$TREADSTONE_SANDBOX_JSON")
echo $TREADSTONE_SANDBOX_JSON`,
      },
    ],
    output: QUICKSTART_CREATE_OUTPUT,
    outputNote: "Needs jq. If status is still creating, wait a few seconds before continuing.",
  },
  {
    n: "04",
    title: "Web UI: hand-off in the browser (urls.web)",
    desc: "Human-facing entry only—not the HTTP proxy. Print the signed `urls.web` link (same shell as step 3).",
    blocks: [
      {
        headerLabel: "bash",
        cmd: 'echo "Web UI (open in a browser):"\necho "$TREADSTONE_WEB_URL"',
      },
    ],
    output: `Web UI (open in a browser):
https://sandbox-${EXAMPLE_SANDBOX_ID}.treadstone-ai.dev/_treadstone/open?token=…`,
    outputNote:
      "The `?token=` query is a signed JWT for this hand-off. Without it, the page is not accessible—share the link only as needed.",
  },
  {
    n: "05",
    title: "HTTP proxy: REST into the sandbox (urls.proxy)",
    desc: "Issue HTTPS requests to `TREADSTONE_PROXY_URL` with a data-plane key—here `POST /v1/shell/exec` runs curl + jq inside the box; pipe the response through jq to show stdout only (sample: Algolia HN front page).",
    blocks: [
      {
        headerLabel: "bash",
        cmd: `export TREADSTONE_API_KEY=$(treadstone --json api-keys create --name "quickstart-proxy-$(date +%s)" --data-plane selected --sandbox-id "$TREADSTONE_SANDBOX_ID" | jq -r '.key')

curl -sS -X POST "\${TREADSTONE_PROXY_URL}/v1/shell/exec" \\
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d @- <<'EOF' | jq -r '(.data // {}).output // empty'
${QUICKSTART_STEP5_SHELL_BODY}
EOF`,
      },
    ],
    output: `Git commands I run before reading any code (2010 points) 
https://piechowski.io/post/git-commands-before-reading-code/

I ported Mac OS X to the Nintendo Wii (1526 points) 
https://bryankeller.github.io/2026/04/08/porting-mac-os-x-nintendo-wii.html

Ask HN: Any interesting niche hobbies? (351 points) 
https://news.ycombinator.com/item?id=47654062

…`,
    outputNote:
      "After the pipe: stdout from the sandbox, not the REST JSON. Keep the heredoc; skip the api-key line if you already exported TREADSTONE_API_KEY. 401/403: check data-plane scope and sandbox id. Image needs curl and jq.",
  },
  {
    n: "06",
    title: "MCP: connect over urls.mcp",
    desc: "MCP over HTTPS at `urls.mcp` (distinct from the HTTP proxy base). Emit a generic `mcpServers` snippet with that URL and `Authorization: Bearer …`.",
    blocks: [
      {
        headerLabel: "bash",
        cmd: `export TREADSTONE_API_KEY=$(treadstone --json api-keys create --name "quickstart-mcp-$(date +%s)" --data-plane selected --sandbox-id "$TREADSTONE_SANDBOX_ID" | jq -r '.key')

jq -n \\
  --arg id "$TREADSTONE_SANDBOX_ID" \\
  --arg url "$TREADSTONE_MCP_URL" \\
  --arg key "$TREADSTONE_API_KEY" \\
  '{mcpServers: {("treadstone-" + $id): {url: $url, headers: {Authorization: ("Bearer " + $key)}}}}'`,
      },
    ],
    output: `{
  "mcpServers": {
    "treadstone-${EXAMPLE_SANDBOX_ID}": {
      "url": "https://app.treadstone-ai.dev/v1/sandboxes/${EXAMPLE_SANDBOX_ID}/proxy/mcp",
      "headers": {
        "Authorization": "Bearer sk-…"
      }
    }
  }
}`,
    outputNote:
      "Copy stdout into your client’s MCP settings. Skip the export if `TREADSTONE_API_KEY` is already set (e.g. step 5). Treat keys like passwords—do not commit.",
  },
]

// ── Plans data ───────────────────────────────────────────────────────────────

const PLANS = [
  {
    name: "Free trial",
    price: "$0",
    period: "Usage metered in CU-hours",
    badge: "AVAILABLE NOW",
    badgeSoon: false,
    desc: "Full CLI, SDK, and API for creating and managing sandboxes. Your dashboard shows CU-hour usage over time.",
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
    highlighted: true,
    waitlistTier: null as string | null,
  },
  {
    name: "Pro",
    price: "Apply for free",
    period: "Higher limits on approval",
    badge: "EARLY ACCESS",
    badgeSoon: false,
    desc: "More compute, concurrency, and storage for steady workloads. We review applications and enable matching quotas.",
    features: [
      "80\u00a0CU-h compute / month (target)",
      "3 concurrent sandboxes",
      "All templates up to aio-sandbox-medium",
      "10\u00a0GiB persistent storage",
      "8\u00a0hr max auto-stop interval",
      "Usage analytics & reporting",
      "Priority support",
    ],
    cta: "Apply for free",
    ctaHref: null,
    highlighted: false,
    waitlistTier: "pro",
  },
  {
    name: "Ultra",
    price: "Apply for free",
    period: "Higher limits on approval",
    badge: "EARLY ACCESS",
    badgeSoon: false,
    desc: "Maximum headroom for heavy jobs and longer sandboxes. Tell us what you are building—we align limits to your use case.",
    features: [
      "240\u00a0CU-h compute / month (target)",
      "5 concurrent sandboxes",
      "All templates up to aio-sandbox-medium",
      "30\u00a0GiB persistent storage",
      "24\u00a0hr max auto-stop interval",
      "Dedicated integrations support",
    ],
    cta: "Apply for free",
    ctaHref: null,
    highlighted: false,
    waitlistTier: "ultra",
  },
  {
    name: "Custom",
    price: "Let's talk",
    period: "Enterprise",
    badge: "CONTACT",
    badgeSoon: false,
    desc: "Negotiated limits and security for teams. We scope capacity and terms together.",
    features: [
      "800\u00a0CU-h compute / month (typical envelope)",
      "10 concurrent sandboxes",
      "100\u00a0GiB persistent storage",
      "72\u00a0hr max auto-stop interval",
      "12\u00a0hr grace period",
      "All sandbox templates",
      "Contact us for terms",
    ],
    cta: "Contact Us",
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
    highlighted: false,
    waitlistTier: null as string | null,
  },
]

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
  const [portfolioUrl, setPortfolioUrl] = useState("")
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
        github_or_portfolio_url: portfolioUrl.trim() || undefined,
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
              REQUEST EARLY ACCESS —{" "}
            </span>
            <span className="text-[11px] font-bold uppercase tracking-[1.5px] text-primary">{tierLabel}</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground transition-colors hover:text-foreground">
            ✕
          </button>
        </div>

        {submitted ? (
          <div className="px-5 py-10 text-center">
            <p className="text-lg font-semibold text-primary">Application submitted</p>
            <p className="mt-2 text-sm text-muted-foreground">
              We&apos;ll review your request and upgrade your account to the {tierLabel} plan when approved. Sign up at{" "}
              <Link to="/auth/sign-up" className="text-primary underline" onClick={onClose}>
                treadstone-ai.dev
              </Link>{" "}
              using the same email if you haven&apos;t already. We only use links you provided to evaluate this
              request.
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
              Early {tierLabel} capacity is limited. We review requests to prioritize builders who will ship on
              Treadstone. There is no minimum GitHub stars or followers—optional links just help us understand your
              background.
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
              <label className="text-[11px] font-medium text-muted-foreground">Company or project (optional)</label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Inc. or side project name"
                className="h-[36px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                GitHub profile or portfolio URL (optional)
              </label>
              <input
                type="url"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                placeholder="https://github.com/yourhandle"
                className="h-[36px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <p className="text-[10px] leading-snug text-muted-foreground/70">
                HTTPS only. Helps us see your work—no star count requirement.
              </p>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                What are you building?{" "}
                {useCaseRequired ? (
                  <span className="text-destructive">*</span>
                ) : (
                  <span className="text-muted-foreground/50">(optional for Pro)</span>
                )}
              </label>
              <p className="text-[10px] leading-snug text-muted-foreground/70">
                Examples: a multi-agent system using sandboxes as execution, trying new agent workflows, or a personal
                cloud dev machine. A few sentences is enough.
              </p>
              <textarea
                required={useCaseRequired}
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                placeholder="e.g. Multi-agent coding agents with isolated runtimes via treadstone CLI; evaluating long-running sandboxes for browser hand-off."
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
                {submit.isPending ? "Submitting…" : "Submit request"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function QuickstartStepCard({
  step,
  isLast,
  endGroup,
  anchorId,
}: {
  step: (typeof QUICKSTART_STEPS)[number]
  isLast: boolean
  /** When true, no vertical connector below this step (e.g. end of the first group before the next section). */
  endGroup?: boolean
  /** Deep-link target for “Install CLI” (step 01). */
  anchorId?: string
}) {
  const [copiedBlockIndex, setCopiedBlockIndex] = useState<number | null>(null)

  const copyBlock = (blockIndex: number, text: string) => {
    navigator.clipboard.writeText(text).catch(() => {})
    setCopiedBlockIndex(blockIndex)
    setTimeout(() => setCopiedBlockIndex(null), 1600)
  }

  return (
    <div
      id={anchorId}
      className={["flex min-w-0 gap-5 sm:gap-8", anchorId ? "scroll-mt-28" : ""].join(" ")}
    >
      {/* Left: step number + vertical connector (stretches with row height) */}
      <div className="flex w-9 shrink-0 flex-col items-center self-stretch pt-0.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/[0.08] font-mono text-[11px] font-bold text-primary">
          {step.n}
        </div>
        {!isLast && !endGroup && (
          <div
            className="mt-3 min-h-[2rem] w-px flex-1 basis-0 bg-gradient-to-b from-primary/35 via-border/50 to-border/40"
            aria-hidden
          />
        )}
      </div>

      {/* Right: content — min-w-0 so long pre/output lines scroll instead of stretching flex width */}
      <div className={["min-w-0 flex-1", isLast ? "pb-0" : "pb-8"].join(" ")}>
        <div className="text-[15px] font-semibold tracking-[-0.01em]">{step.title}</div>
        <p className="mt-1.5 mb-3 text-[13.5px] leading-[1.6] text-muted-foreground">{step.desc}</p>

        {step.blocks.map((block, bi) => (
          <div key={bi} className={bi < step.blocks.length - 1 ? "mb-4 min-w-0" : "min-w-0"}>
            <div className="min-w-0 overflow-hidden rounded-xl border border-border/20 bg-background">
              <div className="flex items-center justify-between border-b border-border/20 bg-white/[0.03] px-5 py-2.5">
                <span className="font-mono text-[11px] text-muted-foreground/50">{block.headerLabel}</span>
                <CopyButton copied={copiedBlockIndex === bi} onCopy={() => copyBlock(bi, block.cmd)} />
              </div>
              <pre
                role="button"
                tabIndex={0}
                title="Click to copy this block"
                onClick={() => copyBlock(bi, block.cmd)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    copyBlock(bi, block.cmd)
                  }
                }}
                className={[
                  "min-w-0 max-w-full cursor-pointer overflow-x-auto whitespace-pre px-5 py-4 font-mono text-[12.5px] leading-[1.7] text-foreground/90 transition-colors",
                  "hover:bg-white/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  copiedBlockIndex === bi ? "bg-primary/[0.06]" : "",
                ].join(" ")}
              >
                {block.cmd}
              </pre>
            </div>
          </div>
        ))}

        {step.output ? (
          <div className="mt-3 max-w-full min-w-0 overflow-x-auto whitespace-pre rounded-lg border border-border/10 bg-white/[0.015] px-4 py-3 text-left font-mono text-[11.5px] leading-[1.55] text-primary/80 sm:text-[12px]">
            {step.output}
          </div>
        ) : null}

        {step.outputNote ? (
          <p className="mt-2.5 font-mono text-[11px] leading-[1.5] text-muted-foreground/50">{step.outputNote}</p>
        ) : null}
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
    <div className="w-full max-w-[740px] overflow-hidden rounded-xl border border-border/20 bg-black/40 text-left">
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
  const [waitlistTier, setWaitlistTier] = useState<string | null>(null)

  useEffect(() => {
    const detachJsonLd = attachLandingJsonLd()
    const previousTitle = document.title
    document.title = LANDING_PAGE_TITLE
    return () => {
      detachJsonLd()
      document.title = previousTitle
    }
  }, [])

  return (
    <main>
      {waitlistTier && <WaitlistDialog tier={waitlistTier} onClose={() => setWaitlistTier(null)} />}

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section
        className="relative overflow-hidden px-6 pb-7 pt-10 sm:px-8 sm:pb-9 sm:pt-14"
        aria-labelledby="landing-hero-heading"
      >
        {/* Glow */}
        <div
          className="pointer-events-none absolute left-1/2 top-0 -z-0 h-[600px] w-[700px] -translate-x-1/2 -translate-y-1/4"
          style={{ background: "radial-gradient(ellipse, rgba(29,255,138,0.06) 0%, transparent 65%)" }}
        />

        <div
          className={[
            "relative z-10 mx-auto flex w-full max-w-[1200px] flex-col items-center gap-10",
            SHOW_HERO_TERMINAL ? "lg:flex-row lg:items-center lg:gap-12 xl:gap-16" : "",
          ].join(" ")}
        >
          {/* Copy column */}
          <div
            className={[
              "flex w-full min-w-0 flex-1 flex-col items-center text-center",
              SHOW_HERO_TERMINAL ? "lg:max-w-[min(28rem,100%)] lg:flex-none xl:max-w-[min(32rem,100%)]" : "",
            ].join(" ")}
          >
            {/* Badge */}
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/[0.08] px-4 py-1.5">
              <span className="size-[6px] animate-pulse rounded-full bg-primary" />
              <span className="font-mono text-[11px] font-medium tracking-[0.04em] text-primary">
                Agent-native sandbox infrastructure
              </span>
            </div>

            <h1
              id="landing-hero-heading"
              className="text-balance font-mono text-[clamp(2.25rem,4.8vw,3.75rem)] font-semibold leading-[1.08] tracking-[-0.04em]"
            >
              Sandboxes for agents
              <br />
              <span className="text-primary">that don't wait for humans.</span>
            </h1>

            <p className="mt-4 w-full max-w-[min(34rem,100%)] text-[17px] leading-[1.65] text-muted-foreground">
              Run isolated sandboxes for coding, browsing, and long-running tasks—driven entirely by your agent via CLI,
              SDK, or API.
            </p>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <a
                href={PUBLIC_DEMO_SANDBOX_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-[10px] bg-primary px-7 py-3.5 text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Try the live demo
              </a>
              <button
                type="button"
                onClick={() => {
                  setWaitlistTier("pro")
                  document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth", block: "start" })
                  window.history.replaceState(null, "", "#pricing")
                }}
                className="rounded-[10px] border border-border/30 px-7 py-3.5 text-[15px] font-semibold text-muted-foreground transition-colors hover:border-border/50 hover:bg-white/[0.04] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Apply for Free access
              </button>
            </div>
          </div>

          {/* Terminal column — hidden when SHOW_HERO_TERMINAL is false; component kept for easy re-enable */}
          {SHOW_HERO_TERMINAL && (
            <div className="flex w-full min-w-0 flex-1 justify-center lg:max-w-none lg:justify-end">
              <AnimatedTerminal />
            </div>
          )}
        </div>
      </section>

      {/* ── CLI Quickstart ────────────────────────────────────── */}
      <section id="quickstart" className="scroll-mt-20 bg-white/[0.015]" aria-label="Quickstart">
        <div className="mx-auto max-w-[1200px] px-6 pb-16 pt-6 sm:px-10 sm:pb-20 sm:pt-8">
          <div className="mx-auto max-w-[960px] text-center">
            <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// quickstart</span>
          </div>

          <div className="mx-auto mt-8 max-w-[960px] text-center">
            <h2 className="font-mono text-[clamp(1.35rem,2.6vw,1.9rem)] font-semibold leading-[1.12] tracking-[-0.03em]">
              Start a sandbox in 3 steps
            </h2>
          </div>

          <div className="mx-auto mt-6 min-w-0 max-w-[960px]">
            {QUICKSTART_STEPS.slice(0, 3).map((step, i) => (
              <QuickstartStepCard
                key={step.n}
                step={step}
                isLast={false}
                endGroup={i === 2}
                anchorId={i === 0 ? "quickstart-step-1" : undefined}
              />
            ))}
          </div>

          <div className="mx-auto mt-14 max-w-[960px] text-center">
            <h2 className="font-mono text-[clamp(1.35rem,2.6vw,1.9rem)] font-semibold leading-[1.12] tracking-[-0.03em]">
              Use your sandbox in 3 ways
            </h2>
          </div>

          <div className="mx-auto mt-6 min-w-0 max-w-[960px]">
            {QUICKSTART_STEPS.slice(3, 6).map((step, i) => (
              <QuickstartStepCard
                key={step.n}
                step={step}
                isLast={i === 2}
                endGroup={false}
              />
            ))}
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 sm:gap-6">
            <Link
              to="/docs/quickstart"
              className="inline-flex items-center gap-1.5 font-mono text-[12.5px] text-primary underline underline-offset-2 hover:text-primary/80"
            >
              Full Quickstart guide →
            </Link>
            <Link
              to="/docs/cli-guide"
              className="inline-flex items-center gap-1.5 font-mono text-[12.5px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              CLI reference →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Plans (anchor id stays `pricing` for nav / #pricing links) ── */}
      <section id="pricing" className="mx-auto max-w-[1080px] scroll-mt-20 px-10 py-24" aria-label="Pricing and plans">
        <div className="mx-auto max-w-[960px] text-center">
          <span className="font-mono text-[11.5px] tracking-[0.08em] text-primary">// free trial</span>
          <h2 className="mt-2 font-mono text-[clamp(1.75rem,3.5vw,2.75rem)] font-semibold leading-[1.1] tracking-[-0.04em]">
            Free trial with metered usage.
            <br />
            Pick a tier that fits your workload.
          </h2>
          <p className="mx-auto mt-3 mb-12 max-w-[520px] text-base leading-[1.65] text-muted-foreground">
            CU-hours reflect how much compute your sandboxes use. Start on the free tier, or apply for higher limits on
            Pro and Ultra when you need more headroom.
          </p>
        </div>

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
              {plan.period ? (
                <div className="mt-1 text-[12px] text-muted-foreground">{plan.period}</div>
              ) : null}

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
    </main>
  )
}
