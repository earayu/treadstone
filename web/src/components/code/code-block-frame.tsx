import type { ReactNode } from "react"

/**
 * Shared chrome for code samples (Landing integrate section, docs Markdown code blocks).
 * Children are the scrollable body — usually a <pre> or <CodeLines />.
 */
export function CodeBlockFrame({
  headerLabel,
  headerRight,
  children,
  className,
}: {
  headerLabel: string
  headerRight?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={[
        "overflow-hidden rounded-xl border border-border/20 bg-background",
        className ?? "",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-border/20 bg-white/[0.03] px-5 py-2.5">
        <span className="font-mono text-[11px] text-muted-foreground/50">{headerLabel}</span>
        {headerRight}
      </div>
      {children}
    </div>
  )
}
