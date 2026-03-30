import { render, screen, waitFor } from "@testing-library/react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DocsPage } from "@/pages/public/docs"

const manifest = [
  {
    slug: "index",
    title: "Start Here",
    section: "Start Here",
    order: 10,
    summary: "What Treadstone is.",
    default: true,
    llm_priority: 100,
  },
  {
    slug: "quickstart-agent-cli",
    title: "Quickstart for Agents (CLI)",
    section: "Quickstarts",
    order: 10,
    summary: "CLI path for agents.",
    default: false,
    llm_priority: 100,
  },
  {
    slug: "guide-browser-handoff",
    title: "Browser Handoff",
    section: "Guides",
    order: 10,
    summary: "Create browser hand-off links.",
    default: false,
    llm_priority: 100,
  },
] as const

const docsBySlug: Record<string, string> = {
  index: "# Start Here\n\nHome content.",
  "quickstart-agent-cli": "# Quickstart for Agents (CLI)\n\nCLI content.",
  "guide-browser-handoff": "# Browser Handoff\n\nGuide content.",
}

function renderDocsPage(initialEntry = "/docs") {
  const router = createMemoryRouter([{ path: "/docs", element: <DocsPage /> }], {
    initialEntries: [initialEntry],
  })
  return render(<RouterProvider router={router} />)
}

describe("DocsPage", () => {
  beforeEach(() => {
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
  })

  it("renders the sidebar from the manifest and falls back to the default page", async () => {
    renderDocsPage("/docs")

    expect(await screen.findByText("Home content.")).toBeInTheDocument()
    expect(screen.getByText("Quickstarts")).toBeInTheDocument()
    expect(screen.getByText("Guides")).toBeInTheDocument()
    expect(screen.getAllByText("Quickstart for Agents (CLI)").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Browser Handoff").length).toBeGreaterThan(0)
  })

  it("uses manifest order for previous and next navigation", async () => {
    renderDocsPage("/docs?page=quickstart-agent-cli")

    expect(await screen.findByText("CLI content.")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Previous.*Start Here/i })).toHaveAttribute(
        "href",
        "/docs?page=index",
      )
      expect(screen.getByRole("link", { name: /Next.*Browser Handoff/i })).toHaveAttribute(
        "href",
        "/docs?page=guide-browser-handoff",
      )
    })
  })
})
