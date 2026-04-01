import {
  Children,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { Link, useNavigate, useParams } from "react-router"
import ReactMarkdown from "react-markdown"
import type { Components } from "react-markdown"
import remarkGfm from "remark-gfm"
import { ChevronRight, Copy, Menu, X } from "lucide-react"

import { CodeBlockFrame } from "@/components/code/code-block-frame"
import { CodeLines } from "@/components/code/code-lines"
import { CopyButton } from "@/components/code/copy-button"
import { parseCodeLines } from "@/components/code/parse-code-lines"
import {
  type DocsManifestEntry,
  fetchDocsManifest,
  getCanonicalDocSlug,
  groupDocsBySection,
  resolveCurrentDoc,
} from "@/lib/docs"
import { splitSurfaceTabMarkdown } from "@/lib/docs-surface-tabs"
import { INTEGRATION_SURFACE_CODE_FRAME_HEADERS } from "@/lib/integration-surface-code-frame-headers"
import { remarkMergeAdjacentCodeBlocks } from "@/lib/remark-merge-adjacent-code-blocks"

interface DocHeading {
  depth: 2 | 3
  id: string
  title: string
}

/** Map `/docs/{slug}.md` (and optional `#hash`) to the SPA docs route so links stay in the styled app. */
function docsMarkdownPathToSpaHref(href: string | undefined): string | null {
  if (!href || href.startsWith("http")) {
    return null
  }
  const m = href.match(/^\/docs\/([a-z0-9-]+)\.md((?:#.*)?)$/i)
  if (!m) {
    return null
  }
  const hash = m[2] ?? ""
  return `/docs/${m[1]}${hash}`
}

/** Derive fence language from `<code class="language-xxx">` inside a `<pre>`. */
function languageFromPreChildren(children: ReactNode): string {
  if (isValidElement(children)) {
    const cls = (children.props as { className?: string }).className ?? ""
    const m = cls.match(/language-([a-zA-Z0-9]+)/)
    return m ? m[1] : "text"
  }
  let found = ""
  Children.forEach(children, (c) => {
    if (found || !isValidElement(c)) {
      return
    }
    const cls = (c.props as { className?: string }).className ?? ""
    const m = cls.match(/language-([a-zA-Z0-9]+)/)
    if (m) {
      found = m[1]
    }
  })
  return found || "text"
}

/** Recursively extract the raw text from React children (strips all elements). */
function extractText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return ""
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(extractText).join("")
  if (isValidElement(node)) {
    return extractText((node.props as { children?: ReactNode }).children)
  }
  return ""
}

function DocsCodePre({
  children,
  surfaceHeaderLabel,
}: {
  children: ReactNode
  surfaceHeaderLabel?: string
}) {
  const preRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  const lang = languageFromPreChildren(children)
  const rawText = extractText(children)
  const coloredLines = useMemo(() => parseCodeLines(rawText, lang), [rawText, lang])
  const headerLabel = surfaceHeaderLabel ?? lang

  const copyAll = useCallback(() => {
    const el = preRef.current
    if (!el) return
    void navigator.clipboard.writeText(el.innerText ?? "").catch(() => {})
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }, [])

  return (
    <CodeBlockFrame
      className="mb-4"
      headerLabel={headerLabel}
      headerRight={<CopyButton copied={copied} onCopy={copyAll} />}
    >
      <div ref={preRef}>
        <CodeLines lines={coloredLines} />
      </div>
    </CodeBlockFrame>
  )
}

function Sidebar({
  currentSlug,
  sections,
  onNavigate,
}: {
  currentSlug: string
  sections: ReturnType<typeof groupDocsBySection>
  onNavigate: (slug: string) => void
}) {
  return (
    <nav aria-label="Documentation sections" className="flex flex-col gap-6 py-8">
      {sections.map((section) => (
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
                    {active ? (
                      <ChevronRight className="size-3 shrink-0 text-primary" />
                    ) : (
                      <span className="size-3 shrink-0" />
                    )}
                    {item.title}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function buildMarkdownComponents(headingIdPrefix: string | undefined, surfaceHeaderLabel?: string): Components {
  const idFor = (plainText: string) => {
    const base = slugifyHeading(plainText.trim())
    return headingIdPrefix ? `${headingIdPrefix}-${base}` : base
  }

  return {
    h1: ({ children }) => (
      <h1 className="mb-6 text-3xl font-bold tracking-tight text-foreground">{children}</h1>
    ),
    h2: ({ children, ...props }) => {
      const id = idFor(extractText(children))
      return (
        <h2
          id={id}
          className="scroll-mt-24 mb-4 mt-10 border-b border-border/20 pb-2 text-xl font-semibold text-foreground first:mt-0"
          {...props}
        >
          {children}
        </h2>
      )
    },
    h3: ({ children }) => {
      const id = idFor(extractText(children))
      return (
        <h3 id={id} className="scroll-mt-24 mb-3 mt-7 text-base font-semibold text-foreground first:mt-0">
          {children}
        </h3>
      )
    },
    p: ({ children }) => <p className="mb-4 leading-7 text-muted-foreground">{children}</p>,
    ul: ({ children }) => <ul className="mb-4 ml-4 list-disc space-y-1.5 text-muted-foreground">{children}</ul>,
    ol: ({ children }) => <ol className="mb-4 ml-4 list-decimal space-y-1.5 text-muted-foreground">{children}</ol>,
    li: ({ children }) => <li className="leading-7">{children}</li>,
    a: ({ href, children }) => {
      const spaTo = docsMarkdownPathToSpaHref(href)
      const className =
        "font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
      if (spaTo) {
        return (
          <Link to={spaTo} className={className}>
            {children}
          </Link>
        )
      }
      return (
        <a
          href={href}
          className={className}
          target={href?.startsWith("http") ? "_blank" : undefined}
          rel={href?.startsWith("http") ? "noreferrer" : undefined}
        >
          {children}
        </a>
      )
    },
    code: ({ className, children, ...props }) => {
      const isInline = !className
      if (isInline) {
        return (
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground" {...props}>
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
      <DocsCodePre surfaceHeaderLabel={surfaceHeaderLabel}>{children}</DocsCodePre>
    ),
    blockquote: ({ children }) => (
      <blockquote className="mb-4 border-l-2 border-primary/40 pl-4 italic text-muted-foreground">{children}</blockquote>
    ),
    table: ({ children }) => (
      <div className="mb-4 max-w-full min-w-0 overflow-x-auto rounded border border-border/20 [-webkit-overflow-scrolling:touch]">
        <table className="w-max min-w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border border-border/30 bg-accent px-3 py-2 text-left align-top text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border border-border/30 px-3 py-2 align-top break-words text-muted-foreground">{children}</td>
    ),
    hr: () => <hr className="my-8 border-border/20" />,
    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
    img: ({ src, alt }) => (
      <img
        src={src}
        alt={alt ?? ""}
        className="mx-auto my-6 block h-auto max-w-full rounded-lg border border-border/20"
      />
    ),
  }
}

function MarkdownBlock({
  content,
  headingIdPrefix,
  surfaceHeaderLabel,
}: {
  content: string
  headingIdPrefix?: string
  surfaceHeaderLabel?: string
}) {
  const components = useMemo(
    () => buildMarkdownComponents(headingIdPrefix, surfaceHeaderLabel),
    [headingIdPrefix, surfaceHeaderLabel],
  )
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMergeAdjacentCodeBlocks]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  )
}

function SurfaceTabs({ cli, rest, sdk }: { cli: string; rest: string; sdk: string }) {
  const reactId = useId().replace(/:/g, "")
  const [tab, setTab] = useState(0)
  const items = [
    { key: "cli", label: "CLI", body: cli, dot: "bg-primary", frameHeader: INTEGRATION_SURFACE_CODE_FRAME_HEADERS.cli },
    { key: "rest", label: "REST API", body: rest, dot: "bg-purple-400", frameHeader: INTEGRATION_SURFACE_CODE_FRAME_HEADERS.rest },
    { key: "sdk", label: "Python SDK", body: sdk, dot: "bg-sky-400", frameHeader: INTEGRATION_SURFACE_CODE_FRAME_HEADERS.sdk },
  ] as const

  return (
    <div className="docs-surface-tabs mb-6">
      <div
        role="tablist"
        aria-label="Integration surface"
        className="mb-6 flex w-fit max-w-full flex-wrap overflow-hidden rounded-lg border border-border/20"
      >
        {items.map((item, i, arr) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === i}
            id={`${reactId}-tab-${item.key}`}
            aria-controls={`${reactId}-panel-${item.key}`}
            className={[
              "flex items-center gap-2 px-5 py-2.5 font-mono text-[12.5px] font-medium transition-colors",
              i < arr.length - 1 ? "border-r border-border/20" : "",
              tab === i
                ? "bg-white/[0.06] text-foreground"
                : "text-muted-foreground hover:bg-white/[0.03]",
            ].join(" ")}
            onClick={() => setTab(i)}
          >
            <span className={`size-[7px] shrink-0 rounded-full ${item.dot}`} aria-hidden />
            {item.label}
          </button>
        ))}
      </div>
      {items.map((item, panelIndex) => (
        <div
          key={item.key}
          id={`${reactId}-panel-${item.key}`}
          role="tabpanel"
          aria-labelledby={`${reactId}-tab-${item.key}`}
          hidden={tab !== panelIndex}
          className="min-w-0 pt-1"
        >
          <MarkdownBlock
            content={item.body}
            headingIdPrefix={`${reactId}-${item.key}`}
            surfaceHeaderLabel={item.frameHeader}
          />
        </div>
      ))}
    </div>
  )
}

function MarkdownContent({ content }: { content: string }) {
  const renderedContent = stripLeadingMarkdownTitle(content)
  const segments = useMemo(() => splitSurfaceTabMarkdown(renderedContent), [renderedContent])

  return (
    <div className="docs-prose min-w-0">
      {segments.map((seg, i) => {
        if (seg.type === "markdown") {
          if (!seg.body.trim()) {
            return null
          }
          return <MarkdownBlock key={i} content={seg.body} />
        }
        return <SurfaceTabs key={i} cli={seg.cli} rest={seg.rest} sdk={seg.sdk} />
      })}
    </div>
  )
}

function stripLeadingMarkdownTitle(content: string): string {
  return content.replace(/^\uFEFF?(?:\r?\n)*#\s+[^\r\n]+(?:\r?\n)+(?:\r?\n)*/, "")
}

function slugifyHeading(value: string): string {
  return value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
}

/** Match heading IDs between markdown extraction and rendered headings (strip inline md syntax). */
function headingPlainTextForSlug(raw: string): string {
  let s = raw.trim()
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1")
  s = s.replace(/`([^`]+)`/g, "$1")
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
  return s.trim()
}

function extractDocHeadings(content: string): DocHeading[] {
  const headings: DocHeading[] = []
  const renderedContent = stripLeadingMarkdownTitle(content)
  const lines = renderedContent.split(/\r?\n/)
  let inCodeBlock = false

  for (const line of lines) {
    if (line.trimStart().startsWith("```")) {
      inCodeBlock = !inCodeBlock
      continue
    }

    if (inCodeBlock) {
      continue
    }

    const match = line.match(/^(##|###)\s+(.+?)\s*#*$/)
    if (!match) {
      continue
    }

    const depth = match[1].length as 2 | 3
    const title = match[2].trim()
    headings.push({
      depth,
      id: slugifyHeading(headingPlainTextForSlug(title)),
      title,
    })
  }

  return headings
}

function OnThisPage({ headings }: { headings: DocHeading[] }) {
  if (headings.length === 0) {
    return null
  }

  return (
    <nav
      aria-label="On this page"
      className="rounded-lg border border-border/20 bg-card/50 p-3 shadow-sm backdrop-blur-sm xl:ml-auto xl:max-w-[13.5rem]"
    >
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">On this page</p>
      <ul className="space-y-1">
        {headings.map((heading) => (
          <li key={`${heading.depth}-${heading.id}`}>
            <a
              href={`#${heading.id}`}
              className={`block rounded px-1.5 py-0.5 text-sm leading-snug text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground ${
                heading.depth === 3 ? "ml-2.5 text-[13px]" : ""
              }`}
              onClick={(e) => {
                e.preventDefault()
                const el = document.getElementById(heading.id)
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" })
                  const nextUrl = `${window.location.pathname}#${heading.id}`
                  window.history.replaceState(null, "", nextUrl)
                }
              }}
            >
              {heading.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export function DocsPage() {
  const { slug: slugParam } = useParams<{ slug?: string }>()
  const navigate = useNavigate()
  const [manifest, setManifest] = useState<DocsManifestEntry[]>([])
  const [content, setContent] = useState("")
  const [loadingManifest, setLoadingManifest] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadManifest() {
      setLoadingManifest(true)
      setError(null)
      try {
        const nextManifest = await fetchDocsManifest()
        if (!cancelled) {
          setManifest(nextManifest)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load docs manifest.")
        }
      } finally {
        if (!cancelled) {
          setLoadingManifest(false)
        }
      }
    }

    void loadManifest()

    return () => {
      cancelled = true
    }
  }, [])

  const pageParam = slugParam ?? null
  const currentEntry = manifest.length > 0 ? resolveCurrentDoc(manifest, pageParam) : null
  const canonicalSlug = manifest.length > 0 ? getCanonicalDocSlug(manifest, pageParam) : null
  const sections = groupDocsBySection(manifest)
  const headings = extractDocHeadings(content)
  const [pageCopied, setPageCopied] = useState(false)

  const copyPageMarkdown = useCallback(async () => {
    if (!content) {
      return
    }
    try {
      await navigator.clipboard.writeText(content)
      setPageCopied(true)
      window.setTimeout(() => setPageCopied(false), 1600)
    } catch {
      // Clipboard may be unavailable; avoid surfacing raw errors to the user.
    }
  }, [content])

  useEffect(() => {
    setPageCopied(false)
  }, [currentEntry?.slug])

  useEffect(() => {
    if (!pageParam || !canonicalSlug || pageParam === canonicalSlug) {
      return
    }

    navigate(`/docs/${canonicalSlug}`, { replace: true })
  }, [canonicalSlug, pageParam, navigate])

  /** After markdown renders, scroll to #hash if present (direct links / refresh). */
  useEffect(() => {
    if (loadingContent || !content) {
      return
    }
    const raw = window.location.hash.slice(1)
    if (!raw) {
      return
    }
    const id = decodeURIComponent(raw)
    requestAnimationFrame(() => {
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: "auto", block: "start" })
      }
    })
  }, [content, loadingContent, currentEntry?.slug])

  useEffect(() => {
    if (!currentEntry) {
      return
    }

    let cancelled = false

    async function loadDoc(slug: string) {
      setLoadingContent(true)
      setError(null)
      try {
        const response = await fetch(`/docs/${slug}.md`)
        if (!response.ok) {
          throw new Error(`Failed to load document: ${response.status}`)
        }
        const text = await response.text()
        if (!cancelled) {
          setContent(text)
          if (!window.location.hash) {
            window.scrollTo(0, 0)
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load document.")
          setContent("")
        }
      } finally {
        if (!cancelled) {
          setLoadingContent(false)
        }
      }
    }

    void loadDoc(currentEntry.slug)

    return () => {
      cancelled = true
    }
  }, [currentEntry])

  function goToDoc(slug: string) {
    navigate(`/docs/${slug}`)
    setMobileNavOpen(false)
  }

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] bg-background">
      <aside className="hidden w-72 shrink-0 border-r border-border/20 lg:block">
        <div className="sticky top-0 h-screen overflow-y-auto px-3">
          <Sidebar currentSlug={currentEntry?.slug ?? ""} sections={sections} onNavigate={goToDoc} />
        </div>
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
          />
          <aside className="absolute left-0 top-0 h-full w-72 overflow-y-auto border-r border-border/20 bg-background px-3">
            <div className="flex h-14 items-center justify-between border-b border-border/20 px-3">
              <span className="text-sm font-semibold">Documentation</span>
              <button
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <Sidebar currentSlug={currentEntry?.slug ?? ""} sections={sections} onNavigate={goToDoc} />
          </aside>
        </div>
      )}

      <main className="min-w-0 flex-1">
        <div className="sticky top-0 z-10 border-b border-border/20 bg-background/90 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setMobileNavOpen(true)}
              className="inline-flex items-center gap-2 rounded border border-border/20 px-3 py-1.5 text-sm text-foreground"
            >
              <Menu className="size-4" />
              Browse Docs
            </button>
            <span className="max-w-[14rem] truncate text-sm font-medium text-foreground">
              {currentEntry?.title ?? "Documentation"}
            </span>
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl px-6 py-10 lg:px-10">
          {loadingManifest ? (
            <p className="text-sm text-muted-foreground">Loading documentation…</p>
          ) : error ? (
            <div className="rounded border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {error}
            </div>
          ) : currentEntry ? (
            <div className="flex flex-col gap-8 xl:flex-row xl:items-stretch xl:justify-between xl:gap-10 2xl:gap-14">
              <div className="min-w-0 min-h-0 flex-1">
                <div className="mb-10">
                  {!currentEntry.default ? (
                    <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      {currentEntry.section}
                    </p>
                  ) : null}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-x-4 sm:gap-y-2">
                    <h1 className="min-w-0 flex-1 pr-2 text-3xl font-bold tracking-tight text-foreground">
                      {currentEntry.title}
                    </h1>
                    <button
                      type="button"
                      disabled={loadingContent || !content}
                      onClick={() => void copyPageMarkdown()}
                      aria-label="Copy page as Markdown"
                      className="inline-flex shrink-0 items-center gap-2 self-end rounded-full border border-border/35 bg-muted/30 px-3 py-1.5 text-sm text-muted-foreground shadow-sm transition-colors hover:border-border/55 hover:bg-muted/50 hover:text-foreground focus-visible:outline focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 sm:self-start sm:pt-1"
                    >
                      <Copy className="size-4 shrink-0 opacity-90" aria-hidden />
                      {pageCopied ? "Copied" : "Copy page"}
                    </button>
                  </div>
                </div>

                {loadingContent ? (
                  <p className="text-sm text-muted-foreground">Loading page…</p>
                ) : (
                  <MarkdownContent content={content} />
                )}
              </div>
              {!loadingContent && headings.length > 0 ? (
                <aside className="relative shrink-0 xl:w-56 xl:pl-1">
                  <div className="xl:sticky xl:top-20 xl:z-10 xl:max-h-[calc(100vh-5.5rem)] xl:overflow-y-auto">
                    <OnThisPage headings={headings} />
                  </div>
                </aside>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No documentation pages found.</p>
          )}
        </div>
      </main>
    </div>
  )
}
