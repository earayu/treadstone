/**
 * Merge consecutive fenced code blocks into one so the docs UI shows a single
 * frame (command + JSON output, or multiple commands) with one copy action.
 *
 * Runs of `code` nodes are merged when separated only by empty / whitespace-only
 * paragraphs (typical blank line between ``` fences). Non-empty prose between
 * blocks keeps them separate.
 */

type CodeNode = {
  type: "code"
  lang?: string | null
  meta?: string | null
  value: string
}

type ParagraphNode = {
  type: "paragraph"
  children?: Array<{ type: string; value?: string }>
}

type MdastNode = {
  type: string
  children?: MdastNode[]
  lang?: string | null
  meta?: string | null
  value?: string
}

export function remarkMergeAdjacentCodeBlocks() {
  return function (tree: { children: MdastNode[] }) {
    mergeRecursive(tree)
  }
}

function mergeRecursive(node: unknown): void {
  if (!node || typeof node !== "object" || !("children" in node)) {
    return
  }
  const n = node as { children: MdastNode[] }
  if (!Array.isArray(n.children)) {
    return
  }
  n.children = mergeCodeRunsInArray(n.children)
  for (const child of n.children) {
    mergeRecursive(child)
  }
}

function mergeCodeRunsInArray(children: MdastNode[]): MdastNode[] {
  const out: MdastNode[] = []
  let i = 0
  while (i < children.length) {
    const node = children[i]
    if (node.type === "code") {
      const run: CodeNode[] = [node as CodeNode]
      let j = i + 1
      while (j < children.length) {
        const gap = children[j]
        if (gap.type === "code") {
          run.push(gap as CodeNode)
          j++
        } else if (isIgnorableGapBetweenCode(gap)) {
          j++
        } else {
          break
        }
      }
      out.push(run.length === 1 ? run[0] : mergeCodeRun(run))
      i = j
    } else {
      out.push(node)
      i++
    }
  }
  return out
}

function isIgnorableGapBetweenCode(node: MdastNode): boolean {
  if (node.type === "paragraph") {
    return paragraphIsEffectivelyEmpty(node as ParagraphNode)
  }
  return false
}

function paragraphIsEffectivelyEmpty(p: ParagraphNode): boolean {
  if (!p.children || p.children.length === 0) {
    return true
  }
  return p.children.every((c) => {
    if (c.type === "text") {
      return (c.value ?? "").trim() === ""
    }
    return false
  })
}

function mergeCodeRun(run: CodeNode[]): CodeNode {
  const langs = run.map((c) => (c.lang ?? "text").trim() || "text")
  const uniform = langs.every((l) => l === langs[0])
  const lang = uniform ? langs[0] : "text"
  return {
    type: "code",
    lang,
    meta: undefined,
    value: run.map((c) => c.value).join("\n\n"),
  }
}
