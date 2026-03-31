import { type CodeLine, cm, pr, fg, ok, js, kw, fn } from "./code-lines"

/**
 * Parse raw code text into colored CodeLine[] using the same palette as Landing.
 * `lang` comes from the Markdown fence (```bash, ```json, ```python, etc.).
 */
export function parseCodeLines(text: string, lang: string): CodeLine[] {
  const lines = text.split("\n")
  const normalizedLang = lang.toLowerCase()

  if (normalizedLang === "json") {
    return lines.map(jsonLine)
  }
  if (normalizedLang === "python" || normalizedLang === "py") {
    return lines.map(pythonLine)
  }
  return lines.map(bashLine)
}

function bashLine(raw: string): CodeLine {
  if (raw === "") return []

  if (/^#\s/.test(raw) || raw === "#") {
    return [{ cls: cm, text: raw }]
  }

  if (/^\$\s/.test(raw)) {
    return [{ cls: pr, text: "$ " }, { cls: fg, text: raw.slice(2) }]
  }

  if (/^✓/.test(raw) || /^Installed:/.test(raw)) {
    return [{ cls: ok, text: raw }]
  }

  if (/^[[{"]/.test(raw) || /^[}\]]/.test(raw)) {
    return [{ cls: js, text: raw }]
  }

  const trimmed = raw.trimStart()
  if (/^[[{"]/.test(trimmed) || /^[}\]]/.test(trimmed)) {
    return [{ cls: js, text: raw }]
  }

  if (/^"[^"]*":/.test(trimmed)) {
    return [{ cls: js, text: raw }]
  }

  return [{ cls: fg, text: raw }]
}

function jsonLine(raw: string): CodeLine {
  if (raw === "") return []
  return [{ cls: js, text: raw }]
}

function pythonLine(raw: string): CodeLine {
  if (raw === "") return []

  if (/^#\s/.test(raw) || raw === "#") {
    return [{ cls: cm, text: raw }]
  }

  const fromMatch = raw.match(/^(from\s+)(\S+\s+)(import\s+)(.+)$/)
  if (fromMatch) {
    return [
      { cls: kw, text: fromMatch[1] },
      { cls: fg, text: fromMatch[2] },
      { cls: kw, text: fromMatch[3] },
      { cls: fg, text: fromMatch[4] },
    ]
  }

  const importMatch = raw.match(/^(import\s+)(.+)$/)
  if (importMatch) {
    return [
      { cls: kw, text: importMatch[1] },
      { cls: fg, text: importMatch[2] },
    ]
  }

  const inlineComment = raw.match(/^(.+?)(#\s.*)$/)
  if (inlineComment) {
    const code = inlineComment[1]
    const comment = inlineComment[2]
    return [...pythonCodeSegments(code), { cls: cm, text: comment }]
  }

  return pythonCodeSegments(raw)
}

function pythonCodeSegments(raw: string): CodeLine {
  const segments: CodeLine = []
  const re = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = re.exec(raw)) !== null) {
    if (match.index > last) {
      segments.push(...pythonPlain(raw.slice(last, match.index)))
    }
    segments.push({ cls: ok, text: match[0] })
    last = re.lastIndex
  }

  if (last < raw.length) {
    segments.push(...pythonPlain(raw.slice(last)))
  }

  return segments.length > 0 ? segments : [{ cls: fg, text: raw }]
}

function pythonPlain(text: string): CodeLine {
  if (!text) return []

  const parts: CodeLine = []
  const re = /\b(print|len|range|str|int|float|list|dict|set|type|isinstance|getattr|setattr|hasattr|super|open|input)\s*(?=\()/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ cls: fg, text: text.slice(last, match.index) })
    }
    parts.push({ cls: fn, text: match[1] })
    last = match.index + match[1].length
  }

  if (last < text.length) {
    parts.push({ cls: fg, text: text.slice(last) })
  }

  return parts
}
