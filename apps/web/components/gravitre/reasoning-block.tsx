import { cn } from "@/lib/utils"
import { Brain, Search, FileText, Lightbulb, LucideIcon } from "lucide-react"

type BlockType = "reasoning" | "research" | "summary" | "insight"

interface ReasoningBlockProps {
  type: BlockType
  title: string
  content: string
  timestamp?: string
  className?: string
}

const blockConfig: Record<BlockType, { icon: LucideIcon; label: string }> = {
  reasoning: { icon: Brain, label: "Reasoning" },
  research: { icon: Search, label: "Research" },
  summary: { icon: FileText, label: "Summary" },
  insight: { icon: Lightbulb, label: "Insight" },
}

export function ReasoningBlock({
  type,
  title,
  content,
  timestamp,
  className,
}: ReasoningBlockProps) {
  const { icon: Icon, label } = blockConfig[type]

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-4",
        className
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-secondary">
            <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        {timestamp && (
          <span className="text-[10px] text-muted-foreground">{timestamp}</span>
        )}
      </div>

      <h4 className="mb-2 text-sm font-medium text-foreground">{title}</h4>
      <p className="text-xs leading-relaxed text-muted-foreground">{content}</p>
    </div>
  )
}
