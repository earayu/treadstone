import { useState } from "react"

/** Landing / docs shared: compact copy control with optional controlled state. */
export function CopyButton({
  text,
  copied,
  onCopy,
  className,
}: {
  text?: string
  copied?: boolean
  onCopy?: () => void
  className?: string
}) {
  const [internalCopied, setInternalCopied] = useState(false)
  const isControlled = copied !== undefined && onCopy !== undefined
  const active = isControlled ? copied : internalCopied

  const handleClick = () => {
    if (isControlled) {
      onCopy!()
    } else {
      navigator.clipboard.writeText(text ?? "").catch(() => {})
      setInternalCopied(true)
      setTimeout(() => setInternalCopied(false), 1600)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={
        className ??
        "inline-flex w-[52px] shrink-0 items-center justify-center rounded border border-border/25 bg-white/[0.04] py-1 font-mono text-[10px] font-medium tracking-wide text-muted-foreground/60 transition-all hover:border-border/50 hover:bg-white/[0.08] hover:text-muted-foreground"
      }
    >
      {active ? "✓ done" : "copy"}
    </button>
  )
}
