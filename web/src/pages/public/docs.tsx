import { useState, useEffect, useCallback } from "react"
import { useSearchParams, Link } from "react-router"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import { Menu, X, ChevronRight } from "lucide-react"
import "highlight.js/styles/github-dark.css"

interface TocSection {
  title: string
  items: TocItem[]
}

interface TocItem {
  slug: string
  title: string
}

const TOC: TocSection[] = [
  {
    title: "Getting Started",
    items: [
      { slug: "getting-started", title: "Overview & Quickstart" },
      { slug: "self-hosting", title: "Self-Hosting" },
    ],
  },
  {
    title: "Reference",
    items: [
      { slug: "cli-reference", title: "CLI Reference" },
      { slug: "sdk-reference", title: "SDK Reference" },
      { slug: "api-reference", title: "API Reference" },
    ],
  },
]

const ALL_ITEMS: TocItem[] = TOC.flatMap((s) => s.items)
const DEFAULT_SLUG = "getting-started"

function Sidebar({
  currentSlug,
  onNavigate,
}: {
  currentSlug: string
  onNavigate: (slug: string) => void
}) {
  return (
    <nav className="flex flex-col gap-6 py-8">
      {TOC.map((section) => (
        <div key={section.title}>
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            {section.title}
          </p>
          <ul className="flex flex-col gap-0.5">
            {section.items.map((item) => {
              const active = item.slug === currentSlug
              return (
                <li key={item.slug}>
                  <button
                    onClick={() => onNavigate(item.slug)}
                    className={`flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm transition-colors ${
                      active
                        ? "bg-accent font-medium text-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                    }`}
                  >
                    {active && <ChevronRight className="size-3 shrink-0 text-primary" />}
                    {!active && <span className="size-3 shrink-0" />}
                    {item.title}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
      <div className="mt-2 border-t border-border/20 pt-4">
        <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Resources
        </p>
        <ul className="flex flex-col gap-0.5">
          <li>
            <a
              href="https://github.com/earayu/treadstone"
              target="_blank"
              rel="noreferrer"
              className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
            >
              <span className="size-3 shrink-0" />
              GitHub
            </a>
          </li>
          <li>
            <a
              href="/docs/sitemap.md"
              className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
            >
              <span className="size-3 shrink-0" />
              Sitemap (for AI)
            </a>
          </li>
        </ul>
      </div>
    </nav>
  )
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="docs-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-6 text-3xl font-bold tracking-tight text-foreground">{children}</h1>
          ),
          h2: ({ children, ...props }) => {
            const id = String(children).toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
            return (
              <h2
                id={id}
                className="mb-4 mt-10 border-b border-border/20 pb-2 text-xl font-semibold text-foreground"
                {...props}
              >
                {children}
              </h2>
            )
          },
          h3: ({ children, ...props }) => {
            const id = String(children).toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
            return (
              <h3 id={id} className="mb-3 mt-7 text-base font-semibold text-foreground" {...props}>
                {children}
              </h3>
            )
          },
          p: ({ children }) => (
            <p className="mb-4 leading-7 text-muted-foreground">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="mb-4 ml-4 list-disc space-y-1.5 text-muted-foreground">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 ml-4 list-decimal space-y-1.5 text-muted-foreground">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-7">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              className="font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
              target={href?.startsWith("http") ? "_blank" : undefined}
              rel={href?.startsWith("http") ? "noreferrer" : undefined}
            >
              {children}
            </a>
          ),
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code
                  className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground"
                  {...props}
                >
                  {children}
                </code>
              )
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="mb-4 overflow-x-auto rounded border border-border/20 bg-[#0d1117] p-4 text-sm">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-4 border-l-2 border-primary/40 pl-4 italic text-muted-foreground">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="mb-4 overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border/30 bg-accent px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border/30 px-4 py-2 text-muted-foreground">{children}</td>
          ),
          hr: () => <hr className="my-8 border-border/20" />,
          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export function DocsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [content, setContent] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const pageParam = searchParams.get("page")
  const currentSlug = ALL_ITEMS.find((i) => i.slug === pageParam) ? pageParam! : DEFAULT_SLUG
  const currentItem = ALL_ITEMS.find((i) => i.slug === currentSlug)!

  const loadDoc = useCallback(async (slug: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/docs/${slug}.md`)
      if (!res.ok) throw new Error(`Failed to load: ${res.status}`)
      const text = await res.text()
      setContent(text)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load document.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDoc(currentSlug)
    window.scrollTo(0, 0)
  }, [currentSlug, loadDoc])

  function navigate(slug: string) {
    setSearchParams({ page: slug })
    setMobileNavOpen(false)
  }

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-border/20 lg:block">
        <div className="sticky top-0 h-screen overflow-y-auto px-3">
          <Sidebar currentSlug={currentSlug} onNavigate={navigate} />
        </div>
      </aside>

      {/* Mobile nav overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
          />
          <aside className="absolute left-0 top-0 h-full w-64 overflow-y-auto border-r border-border/20 bg-background px-3">
            <div className="flex h-14 items-center justify-between border-b border-border/20 px-3">
              <span className="text-sm font-semibold">Docs</span>
              <button
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <Sidebar currentSlug={currentSlug} onNavigate={navigate} />
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 min-w-0">
        {/* Mobile top bar */}
        <div className="flex h-12 items-center gap-3 border-b border-border/20 px-4 lg:hidden">
          <button
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation"
            className="text-muted-foreground hover:text-foreground"
          >
            <Menu className="size-4" />
          </button>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Link to="/docs" className="hover:text-foreground">Docs</Link>
            <ChevronRight className="size-3" />
            <span className="text-foreground">{currentItem.title}</span>
          </div>
        </div>

        <div className="mx-auto max-w-3xl px-6 py-10 lg:px-12 lg:py-12">
          {/* Breadcrumb (desktop) */}
          <div className="mb-8 hidden items-center gap-1.5 text-xs text-muted-foreground lg:flex">
            <Link to="/docs" className="hover:text-foreground transition-colors">Docs</Link>
            <ChevronRight className="size-3" />
            <span className="text-foreground">{currentItem.title}</span>
          </div>

          {loading && (
            <div className="flex flex-col gap-4 animate-pulse">
              <div className="h-8 w-2/3 rounded bg-accent" />
              <div className="h-4 w-full rounded bg-accent/60" />
              <div className="h-4 w-5/6 rounded bg-accent/60" />
              <div className="h-4 w-4/6 rounded bg-accent/60" />
            </div>
          )}

          {error && !loading && (
            <div className="rounded border border-border/20 bg-destructive/10 p-6 text-sm text-destructive">
              <p className="font-medium">Failed to load document</p>
              <p className="mt-1 text-xs opacity-80">{error}</p>
            </div>
          )}

          {!loading && !error && <MarkdownContent content={content} />}

          {/* Page navigation */}
          {!loading && !error && (
            <div className="mt-12 flex items-center justify-between border-t border-border/20 pt-8">
              {(() => {
                const idx = ALL_ITEMS.findIndex((i) => i.slug === currentSlug)
                const prev = ALL_ITEMS[idx - 1]
                const next = ALL_ITEMS[idx + 1]
                return (
                  <>
                    <div>
                      {prev && (
                        <button
                          onClick={() => navigate(prev.slug)}
                          className="group flex flex-col items-start gap-0.5 text-sm"
                        >
                          <span className="text-xs uppercase tracking-wider text-muted-foreground">Previous</span>
                          <span className="font-medium text-foreground transition-colors group-hover:text-primary">
                            ← {prev.title}
                          </span>
                        </button>
                      )}
                    </div>
                    <div>
                      {next && (
                        <button
                          onClick={() => navigate(next.slug)}
                          className="group flex flex-col items-end gap-0.5 text-sm"
                        >
                          <span className="text-xs uppercase tracking-wider text-muted-foreground">Next</span>
                          <span className="font-medium text-foreground transition-colors group-hover:text-primary">
                            {next.title} →
                          </span>
                        </button>
                      )}
                    </div>
                  </>
                )
              })()}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
