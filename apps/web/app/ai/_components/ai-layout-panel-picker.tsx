"use client"

import { LayoutGrid, Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  RESULT_BLOCK_CATALOG,
  type ResultBlockId,
} from "./draggable-result-stack"

type AiLayoutPanelPickerProps = {
  enabledBlocks: ResultBlockId[]
  onToggleBlock: (blockId: ResultBlockId, enabled: boolean) => void
  className?: string
}

export function AiLayoutPanelPicker({
  enabledBlocks,
  onToggleBlock,
  className,
}: AiLayoutPanelPickerProps) {
  const enabledSet = new Set(enabledBlocks)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className={cn("h-8 gap-1.5 text-xs", className)}>
          <LayoutGrid className="h-3.5 w-3.5" />
          <span>Layout panels</span>
          <Plus className="h-3 w-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Add panels to the page</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {RESULT_BLOCK_CATALOG.map((block) => (
          <DropdownMenuCheckboxItem
            key={block.id}
            checked={enabledSet.has(block.id)}
            onCheckedChange={(checked) => onToggleBlock(block.id, checked === true)}
          >
            {block.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
