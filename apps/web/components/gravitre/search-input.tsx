"use client"

import { useState, useRef, type KeyboardEvent } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { Search, X, Loader2, Command } from "lucide-react"
import { Kbd } from "@/components/ui/kbd"

interface SearchInputProps {
  /** Current search value */
  value: string
  /** Callback when value changes */
  onChange: (value: string) => void
  /** Placeholder text */
  placeholder?: string
  /** Show loading indicator */
  loading?: boolean
  /** Show keyboard shortcut hint */
  showShortcut?: boolean
  /** Keyboard shortcut key (default: 'k') */
  shortcutKey?: string
  /** Size variant */
  size?: "sm" | "md" | "lg"
  /** Whether to auto-focus on mount */
  autoFocus?: boolean
  /** Callback when search is submitted (Enter key) */
  onSubmit?: (value: string) => void
  /** Callback when input is cleared */
  onClear?: () => void
  /** Additional className */
  className?: string
  /** Disabled state */
  disabled?: boolean
}

const sizeStyles = {
  sm: {
    container: "h-8",
    icon: "h-3.5 w-3.5",
    input: "text-xs pl-8 pr-7",
    clearBtn: "h-4 w-4 right-2",
  },
  md: {
    container: "h-9",
    icon: "h-4 w-4",
    input: "text-sm pl-9 pr-8",
    clearBtn: "h-5 w-5 right-2.5",
  },
  lg: {
    container: "h-10",
    icon: "h-4 w-4",
    input: "text-sm pl-10 pr-9",
    clearBtn: "h-5 w-5 right-3",
  },
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
  loading = false,
  showShortcut = false,
  shortcutKey = "k",
  size = "md",
  autoFocus = false,
  onSubmit,
  onClear,
  className,
  disabled = false,
}: SearchInputProps) {
  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const styles = sizeStyles[size]

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && onSubmit) {
      onSubmit(value)
    }
    if (e.key === "Escape") {
      inputRef.current?.blur()
      if (value && onClear) {
        onChange("")
        onClear()
      }
    }
  }

  const handleClear = () => {
    onChange("")
    onClear?.()
    inputRef.current?.focus()
  }

  return (
    <div
      className={cn(
        "relative flex items-center rounded-lg border border-border bg-secondary/50 transition-all",
        styles.container,
        isFocused && "border-blue-500/50 ring-1 ring-blue-500/20",
        disabled && "opacity-50 pointer-events-none",
        className
      )}
    >
      {/* Search icon / Loading indicator */}
      <div className="absolute left-3 flex items-center justify-center">
        {loading ? (
          <Loader2 className={cn(styles.icon, "text-muted-foreground animate-spin")} />
        ) : (
          <Search className={cn(styles.icon, "text-muted-foreground")} />
        )}
      </div>

      {/* Input */}
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoFocus={autoFocus}
        disabled={disabled}
        className={cn(
          "w-full h-full rounded-lg bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none",
          styles.input,
          showShortcut && !value && "pr-14"
        )}
      />

      {/* Clear button */}
      <AnimatePresence>
        {value && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            type="button"
            onClick={handleClear}
            className={cn(
              "absolute flex items-center justify-center rounded-md hover:bg-secondary transition-colors",
              styles.clearBtn
            )}
          >
            <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Keyboard shortcut hint */}
      {showShortcut && !value && !isFocused && (
        <div className="absolute right-2 flex items-center gap-0.5">
          <Kbd>
            <Command className="h-2.5 w-2.5" />
          </Kbd>
          <Kbd>{shortcutKey.toUpperCase()}</Kbd>
        </div>
      )}
    </div>
  )
}

// Debounced search input variant
interface DebouncedSearchInputProps extends Omit<SearchInputProps, "onChange"> {
  /** Callback with debounced value */
  onSearch: (value: string) => void
  /** Debounce delay in ms */
  debounceMs?: number
}

export function DebouncedSearchInput({
  onSearch,
  debounceMs = 300,
  ...props
}: DebouncedSearchInputProps) {
  const [localValue, setLocalValue] = useState(props.value || "")
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const handleChange = (newValue: string) => {
    setLocalValue(newValue)
    
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    
    timeoutRef.current = setTimeout(() => {
      onSearch(newValue)
    }, debounceMs)
  }

  return (
    <SearchInput
      {...props}
      value={localValue}
      onChange={handleChange}
    />
  )
}
