import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DocsPage } from "@/pages/public/docs"

const manifest = [
  {
    slug: "index",
    title: "Overview",
    section: "Get Started",
    order: 10,
    summary: "What Treadstone is.",
    default: true,
    llm_priority: 100,
    aliases: ["quickstart-human"],
  },
  {
    slug: "cli-guide",
    title: "CLI Guide",
    section: "Integrate",
    order: 10,
    summary: "Use the hosted CLI surface.",
    default: false,
    llm_priority: 100,
    aliases: ["quickstart-agent-cli"],
  },
  {
    slug: "browser-handoff",
    title: "Browser Handoff",
    section: "Core Workflows",
    order: 10,
    summary: "Create browser hand-off links.",
    default: false,
    llm_priority: 100,
    aliases: ["guide-browser-handoff"],
  },
] as const

const docsBySlug: Record<string, string> = {
  index: "# Overview\n\n## Get Started\n\nHome content.",
  "cli-guide": "# CLI Guide\n\n## Sign In\n\nCLI content.\n\n### Direct Login\n\nUse flags when needed.",
  "browser-handoff": "# Browser Handoff\n\n## Create A Handoff URL\n\nGuide content.",
}

function renderDocsPage(initialEntry = "/docs") {
  const router = createMemoryRouter([{ path: "/docs", element: <DocsPage /> }], {
    initialEntries: [initialEntry],
  })
  return { router, ...render(<RouterProvider router={router} />) }
}

describe("DocsPage", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    })
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url

        if (url.endsWith("/docs/_manifest.json")) {
          return new Response(JSON.stringify(manifest), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        }

        const slugMatch = url.match(/\/docs\/(.+)\.md$/)
        if (slugMatch) {
          const slug = slugMatch[1]
          return new Response(docsBySlug[slug] ?? "# Missing\n", {
            status: docsBySlug[slug] ? 200 : 404,
            headers: { "Content-Type": "text/markdown" },
          })
        }

        return new Response("not found", { status: 404 })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it("renders the sidebar from the manifest and falls back to the default page", async () => {
    renderDocsPage("/docs")

    expect(await screen.findByText("Home content.")).toBeInTheDocument()

    const sidebar = screen.getByRole("navigation", { name: "Documentation sections" })
    expect(within(sidebar).getByText("Get Started")).toBeInTheDocument()
    expect(within(sidebar).getByText("Core Workflows")).toBeInTheDocument()
    expect(within(sidebar).getByText("Integrate")).toBeInTheDocument()
    expect(within(sidebar).getByRole("button", { name: "CLI Guide" })).toBeInTheDocument()
    expect(within(sidebar).getByRole("button", { name: "Browser Handoff" })).toBeInTheDocument()
  })

  it("renders a single page title even when markdown includes an h1", async () => {
    renderDocsPage("/docs?page=cli-guide")

    expect(await screen.findByText("CLI content.")).toBeInTheDocument()

    const markdownHeading = document.querySelector(".docs-prose h1")
    expect(markdownHeading).toBeNull()
  })

  it("canonicalizes legacy alias query params to the new slug", async () => {
    const { router } = renderDocsPage("/docs?page=quickstart-agent-cli")

    expect(await screen.findByText("CLI content.")).toBeInTheDocument()

    await waitFor(() => {
      expect(router.state.location.search).toBe("?page=cli-guide")
    })
  })

  it("renders an in-page navigation from markdown headings", async () => {
    renderDocsPage("/docs?page=cli-guide")

    expect(await screen.findByText("CLI content.")).toBeInTheDocument()

    const onThisPage = screen.getByRole("navigation", { name: "On this page" })
    expect(onThisPage).toBeInTheDocument()
    expect(within(onThisPage).getByRole("link", { name: "Sign In" })).toHaveAttribute("href", "#sign-in")
    expect(within(onThisPage).getByRole("link", { name: "Direct Login" })).toHaveAttribute("href", "#direct-login")
  })

  it("copies full page markdown to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    })

    renderDocsPage("/docs?page=cli-guide")

    expect(await screen.findByText("CLI content.")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Copy page as Markdown" }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(docsBySlug["cli-guide"])
    })
  })
})
