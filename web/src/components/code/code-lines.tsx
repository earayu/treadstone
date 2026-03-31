export type CodeLine = { cls: string; text: string }[]

export const cm = "text-muted-foreground/50"
export const pr = "text-primary"
export const fg = "text-foreground"
export const ok = "text-emerald-400"
export const js = "text-sky-300"
export const kw = "text-purple-400"
export const fn = "text-sky-300"

export function CodeLines({ lines }: { lines: CodeLine[] }) {
  return (
    <pre className="overflow-x-auto px-6 py-5 font-mono text-[12.5px] leading-[1.75]">
      {lines.map((segments, i) => (
        <div key={i}>
          {segments.map((seg, j) => (
            <span key={j} className={seg.cls}>
              {seg.text}
            </span>
          ))}
        </div>
      ))}
    </pre>
  )
}
