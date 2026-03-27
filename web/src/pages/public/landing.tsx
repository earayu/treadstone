import { Link } from "react-router"
import { Terminal, Globe, Shield, Clock, Cpu, ArrowRight } from "lucide-react"

const FEATURES = [
  {
    icon: Globe,
    title: "Instant Session Links",
    desc: "Generate secure browser links with one click. Share sandbox access via URL with automatic expiration.",
  },
  {
    icon: Shield,
    title: "Proxy-Based Access",
    desc: "Access sandboxes through secure proxy URLs. No direct network exposure, all traffic routed safely.",
  },
  {
    icon: Clock,
    title: "Time-Limited Sessions",
    desc: "Web links auto-expire for security. Monitor last-used timestamps and disable links at any time.",
  },
]

const TEMPLATES = [
  { name: "Tiny", cpu: "0.5", memory: "512 MiB", duration: "30 min", concurrency: 1, cost: "0.5 credits/hr", price: "Free" },
  { name: "Small", cpu: "1", memory: "1 GiB", duration: "20 min", concurrency: 1, cost: "1 credit/hr", price: "Coming Soon" },
  { name: "Medium", cpu: "2", memory: "2 GiB", duration: "30 min", concurrency: 1, cost: "2 credits/hr", price: "Contact Us" },
]

const OPEN_SOURCE_FEATURES = [
  {
    icon: Cpu,
    title: "Instant Spin-up",
    desc: "Deploy complex agentic environments in under 3 seconds using our pre-cached core images.",
  },
  {
    icon: Shield,
    title: "Hardened Isolation",
    desc: "Kernel-level separation ensures that even compromised agents cannot escape their sandbox.",
  },
]

export function LandingPage() {
  return (
    <div>
      {/* Hero */}
      <section className="flex flex-col items-center px-6 pb-24 pt-20 text-center">
        <div className="mb-8 flex items-center gap-2 border border-border/30 px-4 py-1.5 text-[10px] uppercase tracking-widest text-muted-foreground">
          <span className="inline-block size-1.5 bg-primary" />
          System Status: Operational
        </div>
        <h1 className="text-5xl font-bold uppercase leading-tight tracking-tight text-foreground md:text-7xl">
          Sandbox
          <br />
          <span className="text-primary">For AI Agents</span>
        </h1>
        <p className="mt-6 max-w-xl text-base text-muted-foreground">
          Deploy, monitor, and hand-off agentic workflows with microscopic precision.
          A high-density environment engineered for the next generation of autonomous compute.
        </p>
        <div className="mt-10 flex gap-4">
          <Link
            to="/auth/sign-up"
            className="bg-primary px-6 py-3 text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Start Free
          </Link>
          <Link
            to="/quickstart"
            className="border border-border px-6 py-3 text-sm font-bold uppercase tracking-widest text-foreground transition-colors hover:bg-accent"
          >
            Install CLI
          </Link>
        </div>
      </section>

      {/* Browser Hand-off Section */}
      <section className="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">
            Browser
            <br />
            Hand-off
          </h2>
          <div className="mt-8 space-y-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex gap-3">
                <f.icon className="mt-0.5 size-4 shrink-0 text-primary" />
                <div>
                  <h3 className="text-sm font-bold text-foreground">{f.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="overflow-hidden border border-border/15 bg-card p-4">
          <div className="space-y-2 font-mono text-[11px]">
            <div className="text-muted-foreground">
              <span className="text-primary">[READY]</span> Initializing sandbox environment…
            </div>
            <div className="text-muted-foreground">
              <span className="text-primary">[SYNC]</span> Agent dispatched to sandbox: aio-sandbox-tiny
            </div>
            <div className="mt-4 border border-border/10 p-3">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-muted-foreground">
                <span>Active Hand-off Session</span>
                <span className="flex items-center gap-1.5 text-primary">
                  <span className="inline-block size-1.5 rounded-full bg-primary" />
                  Live
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3">
                <div>
                  <div className="text-[10px] text-muted-foreground/60">LINKS</div>
                  <div className="text-xs font-bold text-foreground">0 / 25</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground/60">CPU</div>
                  <div className="text-xs font-bold text-foreground">64 %</div>
                </div>
              </div>
            </div>
            <div className="mt-3 text-muted-foreground">
              <span className="text-primary">[MKT]</span> Exclusive relay: Web link generated.
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <div className="bg-primary px-4 py-2 text-[11px] font-bold uppercase tracking-widest text-primary-foreground">
              Authorize Session
            </div>
            <div className="border border-border px-4 py-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
              Full Preview →
            </div>
          </div>
        </div>
      </section>

      {/* Templates Table */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-[2px] text-muted-foreground">
              Sandbox
            </h2>
            <h2 className="text-sm font-bold uppercase tracking-[2px] text-muted-foreground">
              Templates
            </h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Choose the right compute template for your workload.
            </p>
          </div>
          <Link
            to="/quickstart"
            className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
          >
            Read Full Docs
          </Link>
        </div>

        <div className="mt-8 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border/15 text-left text-[10px] uppercase tracking-[1px] text-muted-foreground">
                <th className="py-3 pr-6 font-bold">Specification</th>
                {TEMPLATES.map((t) => (
                  <th key={t.name} className="py-3 pr-6 font-bold">
                    {t.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-muted-foreground">
              {[
                { label: "vCPU", key: "cpu" as const },
                { label: "Memory", key: "memory" as const },
                { label: "Max Duration", key: "duration" as const },
                { label: "Concurrency", key: "concurrency" as const },
                { label: "Compute Cost", key: "cost" as const },
              ].map((row) => (
                <tr key={row.label} className="border-b border-border/5">
                  <td className="py-3 pr-6 text-muted-foreground/80">{row.label}</td>
                  {TEMPLATES.map((t) => (
                    <td key={t.name} className="py-3 pr-6">
                      {String(t[row.key])}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td className="py-3 pr-6 font-bold uppercase text-foreground">Monthly Price</td>
                {TEMPLATES.map((t) => (
                  <td key={t.name} className="py-3 pr-6 font-bold text-primary">
                    {t.price}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Open Source */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-3xl font-bold tracking-tight text-foreground">Open Source</h2>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Treadstone is open source and self-hostable. Deploy on your own Kubernetes cluster with full control.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {OPEN_SOURCE_FEATURES.map((f) => (
            <div key={f.title} className="border border-border/15 bg-card p-6">
              <f.icon className="size-5 text-primary" />
              <h3 className="mt-3 font-bold text-foreground">{f.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-10 flex gap-4">
          <input
            type="email"
            placeholder="Get started for free"
            className="h-10 w-64 bg-card px-4 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
            readOnly
          />
          <Link
            to="/auth/sign-up"
            className="flex items-center gap-2 bg-primary px-6 py-2 text-sm font-bold uppercase tracking-widest text-primary-foreground"
          >
            Sign Up Free
            <ArrowRight className="size-3" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/10 px-6 py-12">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-4">
          <div>
            <div className="text-sm font-bold uppercase tracking-widest text-primary">
              Treadstone
            </div>
            <div className="mt-2 text-[10px] uppercase tracking-widest text-muted-foreground/60">
              &copy; 2026 Treadstone.
            </div>
          </div>
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              Resources
            </h4>
            <div className="mt-3 space-y-2 text-xs text-muted-foreground">
              <div><Link to="/quickstart" className="hover:text-foreground">API Reference</Link></div>
              <div><Link to="/quickstart" className="hover:text-foreground">Changelog</Link></div>
              <div><Link to="/quickstart" className="hover:text-foreground">Docs</Link></div>
            </div>
          </div>
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              Legal
            </h4>
            <div className="mt-3 space-y-2 text-xs text-muted-foreground">
              <div><a href="#" className="hover:text-foreground">Privacy</a></div>
              <div><a href="#" className="hover:text-foreground">Terms</a></div>
              <div><a href="#" className="hover:text-foreground">Legal</a></div>
            </div>
          </div>
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              Community
            </h4>
            <div className="mt-3 space-y-2 text-xs text-muted-foreground">
              <div><a href="https://github.com/earayu/treadstone" className="hover:text-foreground">GitHub</a></div>
              <div><a href="#" className="hover:text-foreground">Discord</a></div>
            </div>
          </div>
        </div>
      </footer>

      {/* Terminal Decoration */}
      <div className="pointer-events-none fixed bottom-0 right-0 opacity-5">
        <Terminal className="size-96" />
      </div>
    </div>
  )
}
