import { describe, expect, it } from "vitest"

import { remarkMergeAdjacentCodeBlocks } from "@/lib/remark-merge-adjacent-code-blocks"

describe("remarkMergeAdjacentCodeBlocks", () => {
  const run = remarkMergeAdjacentCodeBlocks()

  it("merges two consecutive code blocks into one with lang text when langs differ", () => {
    const tree = {
      type: "root",
      children: [
        { type: "code", lang: "bash", value: "treadstone --json templates list" },
        { type: "code", lang: "json", value: '{"items":[]}' },
      ],
    }
    run(tree as Parameters<typeof run>[0])
    expect(tree.children).toHaveLength(1)
    expect(tree.children[0]).toMatchObject({
      type: "code",
      lang: "text",
      value: 'treadstone --json templates list\n\n{"items":[]}',
    })
  })

  it("keeps a single code block unchanged", () => {
    const tree = {
      type: "root",
      children: [{ type: "code", lang: "bash", value: "echo ok" }],
    }
    run(tree as Parameters<typeof run>[0])
    expect(tree.children).toHaveLength(1)
    expect(tree.children[0]).toMatchObject({ type: "code", lang: "bash", value: "echo ok" })
  })

  it("does not merge when a non-empty paragraph sits between code blocks", () => {
    const tree = {
      type: "root",
      children: [
        { type: "code", lang: "bash", value: "a" },
        { type: "paragraph", children: [{ type: "text", value: "Explanation" }] },
        { type: "code", lang: "bash", value: "b" },
      ],
    }
    run(tree as Parameters<typeof run>[0])
    expect(tree.children).toHaveLength(3)
  })

  it("merges across an empty paragraph", () => {
    const tree = {
      type: "root",
      children: [
        { type: "code", lang: "bash", value: "a" },
        { type: "paragraph", children: [{ type: "text", value: "   " }] },
        { type: "code", lang: "bash", value: "b" },
      ],
    }
    run(tree as Parameters<typeof run>[0])
    expect(tree.children).toHaveLength(1)
    expect(tree.children[0]).toMatchObject({
      type: "code",
      lang: "bash",
      value: "a\n\nb",
    })
  })

  it("merges nested code blocks inside a blockquote", () => {
    const tree = {
      type: "root",
      children: [
        {
          type: "blockquote",
          children: [
            { type: "code", lang: "bash", value: "x" },
            { type: "code", lang: "json", value: "{}" },
          ],
        },
      ],
    }
    run(tree as Parameters<typeof run>[0])
    const bq = tree.children[0] as { children: unknown[] }
    expect(bq.children).toHaveLength(1)
    expect(bq.children[0]).toMatchObject({ type: "code", lang: "text" })
  })
})
