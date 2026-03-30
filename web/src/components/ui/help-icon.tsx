import { CircleHelp, ExternalLink } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip"
import { cn } from "@/lib/utils"

interface HelpIconProps {
  /** Explanation text shown in the tooltip */
  content: string
  /** Optional link shown at the bottom of the tooltip */
  link?: {
    href: string
    label?: string
  }
  /** Icon size variant. Defaults to "sm" (14px) */
  size?: "sm" | "md"
  /** Tooltip placement. Defaults to "top" */
  side?: "top" | "right" | "bottom" | "left"
  className?: string
}

export function HelpIcon({ content, link, size = "sm", side = "top", className }: HelpIconProps) {
  const iconSize = size === "sm" ? "size-3.5" : "size-4"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex shrink-0 cursor-default items-center text-muted-foreground/50 transition-colors hover:text-muted-foreground focus:outline-none",
            className,
          )}
          aria-label="More information"
        >
          <CircleHelp className={iconSize} />
        </button>
      </TooltipTrigger>
      <TooltipContent side={side} className="leading-relaxed">
        <p className="whitespace-pre-line">{content}</p>
        {link && (
          <a
            href={link.href}
            target={link.href.startsWith("http") ? "_blank" : undefined}
            rel={link.href.startsWith("http") ? "noopener noreferrer" : undefined}
            className="mt-1.5 flex items-center gap-1 text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="size-3 shrink-0" />
            {link.label ?? "Learn more"}
          </a>
        )}
      </TooltipContent>
    </Tooltip>
  )
}
