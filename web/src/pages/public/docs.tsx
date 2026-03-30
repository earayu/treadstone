import { useEffect, useState } from "react"
import { useSearchParams } from "react-router"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import { ChevronRight, Menu, X } from "lucide-react"
import "highlight.js/styles/github-dark.css"

import {
  type DocsManifestEntry,
  fetchDocsManifest,
  getCanonicalDocSlug,
  groupDocsBySection,
  resolveCurrentDoc,
} from "@/lib/docs"

interface DocHeading {
  depth: 2 | 3
  id: string
  title: string
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

function MarkdownContent({ content }: { content: string }) {
  const renderedContent = stripLeadingMarkdownTitle(content)

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
            const id = slugifyHeading(String(children))
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
            const id = slugifyHeading(String(children))
            return (
              <h3 id={id} className="mb-3 mt-7 text-base font-semibold text-foreground" {...props}>
                {children}
              </h3>
            )
          },
          p: ({ children }) => <p className="mb-4 leading-7 text-muted-foreground">{children}</p>,
          ul: ({ children }) => <ul className="mb-4 ml-4 list-disc space-y-1.5 text-muted-foreground">{children}</ul>,
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
        {renderedContent}
      </ReactMarkdown>
    </div>
  )
}

function stripLeadingMarkdownTitle(content: string): string {
  return content.replace(/^\uFEFF?(?:\r?\n)*#\s+[^\r\n]+(?:\r?\n)+(?:\r?\n)*/, "")
}

function slugifyHeading(value: string): string {
  return value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
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
      id: slugifyHeading(title),
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
    <nav aria-label="On this page" className="rounded border border-border/20 bg-card/40 p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">On this page</p>
      <ul className="space-y-1.5">
        {headings.map((heading) => (
          <li key={`${heading.depth}-${heading.id}`}>
            <a
              href={`#${heading.id}`}
              className={`block rounded px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground ${
                heading.depth === 3 ? "ml-3 text-[13px]" : ""
              }`}
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
  const [searchParams, setSearchParams] = useSearchParams()
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

  const pageParam = searchParams.get("page")
  const currentEntry = manifest.length > 0 ? resolveCurrentDoc(manifest, pageParam) : null
  const canonicalSlug = manifest.length > 0 ? getCanonicalDocSlug(manifest, pageParam) : null
  const sections = groupDocsBySection(manifest)
  const headings = extractDocHeadings(content)

  useEffect(() => {
    if (!pageParam || !canonicalSlug || pageParam === canonicalSlug) {
      return
    }

    setSearchParams({ page: canonicalSlug }, { replace: true })
  }, [canonicalSlug, pageParam, setSearchParams])

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
          window.scrollTo(0, 0)
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

  function navigate(slug: string) {
    setSearchParams({ page: slug })
    setMobileNavOpen(false)
  }

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] bg-background">
      <aside className="hidden w-72 shrink-0 border-r border-border/20 lg:block">
        <div className="sticky top-0 h-screen overflow-y-auto px-3">
          <Sidebar currentSlug={currentEntry?.slug ?? ""} sections={sections} onNavigate={navigate} />
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
            <Sidebar currentSlug={currentEntry?.slug ?? ""} sections={sections} onNavigate={navigate} />
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

        <div className="mx-auto max-w-4xl px-6 py-10 lg:px-10">
          {loadingManifest ? (
            <p className="text-sm text-muted-foreground">Loading documentation…</p>
          ) : error ? (
            <div className="rounded border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {error}
            </div>
          ) : currentEntry ? (
            <>
              <div className="mb-10">
                {!currentEntry.default ? (
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    {currentEntry.section}
                  </p>
                ) : null}
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{currentEntry.title}</h1>
              </div>

              {loadingContent ? (
                <p className="text-sm text-muted-foreground">Loading page…</p>
              ) : (
                <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_15rem] xl:gap-10">
                  {headings.length > 0 ? (
                    <aside className="order-first mb-8 xl:order-last xl:mb-0 xl:self-start">
                      <div className="xl:sticky xl:top-24">
                        <OnThisPage headings={headings} />
                      </div>
                    </aside>
                  ) : null}

                  <div className="min-w-0">
                    <MarkdownContent content={content} />
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No documentation pages found.</p>
          )}
        </div>
      </main>
    </div>
  )
}
