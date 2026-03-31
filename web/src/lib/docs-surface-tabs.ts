/**
 * Split markdown into alternating blocks. A "surface tab" block is a contiguous
 * ### CLI / ### REST API / ### Python SDK triple (same order). Code fences are
 * skipped when scanning for those headings so fenced content cannot fake a tab.
 */

export type SurfaceTabSegment =
  | { type: "markdown"; body: string }
  | { type: "surfaceTabs"; cli: string; rest: string; sdk: string }

const H3_CLI = "### CLI"
const H3_REST = "### REST API"
const H3_SDK = "### Python SDK"

function trimHeadingLine(line: string): string {
  return line.trim()
}

function isH2(line: string): boolean {
  return trimHeadingLine(line).startsWith("## ") && !trimHeadingLine(line).startsWith("###")
}

/** True if line starts a surface-tab triple at `i` (### CLI, then REST API, then Python SDK before next ##). */
function trySurfaceTabBlock(lines: string[], start: number): { end: number; cli: string; rest: string; sdk: string } | null {
  if (trimHeadingLine(lines[start]) !== H3_CLI) {
    return null
  }

  let inFence = false
  let restLine = -1
  let sdkLine = -1

  for (let j = start + 1; j < lines.length; j++) {
    const raw = lines[j]
    const t = trimHeadingLine(raw)
    if (t.startsWith("```")) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      continue
    }
    if (isH2(raw)) {
      break
    }
    if (t === H3_REST) {
      restLine = j
      break
    }
  }

  if (restLine < 0) {
    return null
  }

  inFence = false
  for (let j = restLine + 1; j < lines.length; j++) {
    const raw = lines[j]
    const t = trimHeadingLine(raw)
    if (t.startsWith("```")) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      continue
    }
    if (isH2(raw)) {
      break
    }
    if (t === H3_SDK) {
      sdkLine = j
      break
    }
  }

  if (sdkLine < 0) {
    return null
  }

  let end = lines.length
  inFence = false
  for (let j = sdkLine + 1; j < lines.length; j++) {
    const raw = lines[j]
    const t = trimHeadingLine(raw)
    if (t.startsWith("```")) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      continue
    }
    if (isH2(raw)) {
      end = j
      break
    }
  }

  const cli = lines.slice(start + 1, restLine).join("\n").trimEnd()
  const rest = lines.slice(restLine + 1, sdkLine).join("\n").trimEnd()
  const sdk = lines.slice(sdkLine + 1, end).join("\n").trimEnd()

  return { end, cli, rest, sdk }
}

export function splitSurfaceTabMarkdown(markdown: string): SurfaceTabSegment[] {
  const lines = markdown.split(/\r?\n/)
  const segments: SurfaceTabSegment[] = []
  let buf: string[] = []
  let i = 0

  while (i < lines.length) {
    const block = trySurfaceTabBlock(lines, i)
    if (block) {
      if (buf.length > 0) {
        segments.push({ type: "markdown", body: buf.join("\n") })
        buf = []
      }
      segments.push({
        type: "surfaceTabs",
        cli: block.cli,
        rest: block.rest,
        sdk: block.sdk,
      })
      i = block.end
    } else {
      buf.push(lines[i])
      i += 1
    }
  }

  if (buf.length > 0) {
    segments.push({ type: "markdown", body: buf.join("\n") })
  }

  return segments
}
