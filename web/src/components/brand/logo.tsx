import { useId } from "react"
import { cn } from "@/lib/utils"

/**
 * Treadstone logo symbol — the T-in-rounded-rect mark.
 * Uses currentColor so it adapts to any text/fill context.
 */
export function TreadstoneSymbol({ className }: { className?: string }) {
  const id = useId()
  const maskId = `ts-sym${id.replace(/:/g, "")}`

  return (
    <svg
      viewBox="0 0 1024 1024"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
        <rect width="1024" height="1024" fill="black" />
        <path
          d="M246 372C246 296.889 306.889 236 382 236H642C717.111 236 778 296.889 778 372V648C778 723.111 717.111 784 642 784H382C306.889 784 246 723.111 246 648V372Z"
          fill="white"
        />
        <polygon points="594,220 794,220 794,420" fill="black" />
        <path
          d="M390 368H634L586 454H556V678C556 702.301 536.301 722 512 722C487.699 722 468 702.301 468 678V454H438L390 368Z"
          fill="black"
        />
      </mask>
      <rect width="1024" height="1024" fill="currentColor" mask={`url(#${maskId})`} />
    </svg>
  )
}

/**
 * Treadstone horizontal lockup — symbol mark + "Treadstone" wordmark side by side.
 */
export function TreadstoneLockup({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <TreadstoneSymbol className="size-[1em]" />
      <span className="font-semibold tracking-tight">Treadstone</span>
    </span>
  )
}
