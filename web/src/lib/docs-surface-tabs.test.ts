import { describe, expect, it } from "vitest"

import { splitSurfaceTabMarkdown } from "./docs-surface-tabs"

describe("splitSurfaceTabMarkdown", () => {
  it("returns a single markdown segment when no surface tab triple exists", () => {
    const md = "## Title\n\nHello\n"
    const segs = splitSurfaceTabMarkdown(md)
    expect(segs).toHaveLength(1)
    expect(segs[0].type).toBe("markdown")
    if (segs[0].type === "markdown") {
      expect(segs[0].body).toContain("Hello")
    }
  })

  it("extracts one CLI / REST API / Python SDK group", () => {
    const md = [
      "## Create",
      "",
      "### CLI",
      "cli body",
      "",
      "### REST API",
      "rest body",
      "",
      "### Python SDK",
      "sdk body",
      "",
      "## Next",
      "tail",
    ].join("\n")

    const segs = splitSurfaceTabMarkdown(md)
    expect(segs).toHaveLength(3)
    expect(segs[0].type).toBe("markdown")
    expect(segs[1].type).toBe("surfaceTabs")
    if (segs[1].type === "surfaceTabs") {
      expect(segs[1].cli).toBe("cli body")
      expect(segs[1].rest).toBe("rest body")
      expect(segs[1].sdk).toBe("sdk body")
    }
    expect(segs[2].type).toBe("markdown")
    if (segs[2].type === "markdown") {
      expect(segs[2].body).toContain("## Next")
    }
  })

  it("ignores ### markers inside fenced code blocks when pairing headings", () => {
    const md = [
      "## S",
      "",
      "### CLI",
      "```text",
      "### REST API",
      "```",
      "",
      "### REST API",
      "ok",
      "",
      "### Python SDK",
      "py",
    ].join("\n")

    const segs = splitSurfaceTabMarkdown(md)
    expect(segs).toHaveLength(2)
    expect(segs[0].type).toBe("markdown")
    expect(segs[1].type).toBe("surfaceTabs")
    if (segs[1].type === "surfaceTabs") {
      expect(segs[1].rest.trim()).toBe("ok")
    }
  })
})
