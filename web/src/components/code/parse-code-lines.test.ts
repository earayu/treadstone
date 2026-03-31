import { describe, expect, it } from "vitest"

import { cm, pr, fg, ok, js, kw, fn } from "./code-lines"
import { parseCodeLines } from "./parse-code-lines"

describe("parseCodeLines", () => {
  describe("bash", () => {
    it("colors comment lines", () => {
      const lines = parseCodeLines("# hello", "bash")
      expect(lines).toEqual([[{ cls: cm, text: "# hello" }]])
    })

    it("adds green $ prompt to commands", () => {
      const lines = parseCodeLines("$ treadstone auth login", "bash")
      expect(lines).toEqual([
        [{ cls: pr, text: "$ " }, { cls: fg, text: "treadstone auth login" }],
      ])
    })

    it("colors success output lines", () => {
      const lines = parseCodeLines("✓ Logged in", "bash")
      expect(lines).toEqual([[{ cls: ok, text: "✓ Logged in" }]])
    })

    it("colors JSON output lines in sky", () => {
      const lines = parseCodeLines('{"id": "sb_123"}', "bash")
      expect(lines).toEqual([[{ cls: js, text: '{"id": "sb_123"}' }]])
    })

    it("colors indented JSON lines", () => {
      const lines = parseCodeLines('  "name": "demo",', "bash")
      expect(lines).toEqual([[{ cls: js, text: '  "name": "demo",' }]])
    })

    it("treats plain text as fg", () => {
      const lines = parseCodeLines("something else", "bash")
      expect(lines).toEqual([[{ cls: fg, text: "something else" }]])
    })

    it("handles empty lines", () => {
      const lines = parseCodeLines("# a\n\n$ b", "bash")
      expect(lines).toHaveLength(3)
      expect(lines[1]).toEqual([])
    })
  })

  describe("json", () => {
    it("colors all lines in sky", () => {
      const lines = parseCodeLines('{\n  "key": "val"\n}', "json")
      expect(lines).toEqual([
        [{ cls: js, text: "{" }],
        [{ cls: js, text: '  "key": "val"' }],
        [{ cls: js, text: "}" }],
      ])
    })
  })

  describe("python", () => {
    it("splits from/import statements", () => {
      const lines = parseCodeLines("from foo import Bar", "python")
      expect(lines).toEqual([
        [
          { cls: kw, text: "from " },
          { cls: fg, text: "foo " },
          { cls: kw, text: "import " },
          { cls: fg, text: "Bar" },
        ],
      ])
    })

    it("colors inline comments", () => {
      const lines = parseCodeLines('print(x) # "hello"', "python")
      expect(lines[0].at(-1)).toMatchObject({ cls: cm })
    })

    it("highlights print as a function name", () => {
      const lines = parseCodeLines("print(x)", "python")
      expect(lines[0][0]).toMatchObject({ cls: fn, text: "print" })
    })

    it("highlights string literals in ok color", () => {
      const lines = parseCodeLines('name="hello"', "python")
      const okSegs = lines[0].filter((s) => s.cls === ok)
      expect(okSegs.length).toBeGreaterThan(0)
      expect(okSegs[0].text).toBe('"hello"')
    })

    it("colors comments", () => {
      const lines = parseCodeLines("# this is a comment", "python")
      expect(lines).toEqual([[{ cls: cm, text: "# this is a comment" }]])
    })
  })

  describe("text / unknown", () => {
    it("falls back to bash rules for unknown langs", () => {
      const lines = parseCodeLines("$ echo hi", "text")
      expect(lines[0][0]).toMatchObject({ cls: pr, text: "$ " })
    })
  })
})
