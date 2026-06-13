"use client"

import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

export function FollowUpSuggestions({
  suggestions,
  onSelect,
  visible,
}: {
  suggestions: string[]
  onSelect: (text: string) => void
  visible: boolean
}) {
  if (!visible || suggestions.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {suggestions.map((text, i) => (
        <motion.button
          key={`${text}-${i}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1, duration: 0.3 }}
          onClick={() => onSelect(text)}
          className={cn(
            "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs",
            "border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 hover:border-emerald-300 transition-colors",
          )}
        >
          <span className="truncate max-w-[240px]">{text.length > 40 ? `${text.slice(0, 40)}…` : text}</span>
          <ArrowRight className="h-3 w-3 shrink-0 text-zinc-400" />
        </motion.button>
      ))}
    </div>
  )
}
