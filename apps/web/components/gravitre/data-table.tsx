"use client"

import { cn } from "@/lib/utils"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"

interface Column<T> {
  key: string
  header: string
  className?: string
  render?: (item: T) => React.ReactNode
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  onRowClick?: (item: T) => void
  className?: string
  /** Override auto-generated mobile cards */
  mobileFallback?: React.ReactNode
}

function DefaultMobileCards<T extends { id: string | number }>({
  columns,
  data,
  onRowClick,
}: Pick<DataTableProps<T>, "columns" | "data" | "onRowClick">) {
  const primary = columns[0]
  const secondary = columns.slice(1, 3)

  return (
    <ul className="space-y-2">
      {data.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            onClick={() => onRowClick?.(item)}
            className={cn(
              "flex w-full flex-col gap-1 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3 text-left shadow-[var(--np-shadow)]",
              onRowClick && "transition-colors hover:bg-[color:var(--g-surface-2)]",
            )}
          >
            <div className="text-sm font-medium text-[color:var(--g-text-primary)]">
              {primary?.render
                ? primary.render(item)
                : ((item as Record<string, unknown>)[primary?.key ?? ""] as React.ReactNode)}
            </div>
            {secondary.length > 0 ? (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[color:var(--g-text-muted)]">
                {secondary.map((column) => (
                  <span key={column.key} className="min-w-0 truncate">
                    {column.render
                      ? column.render(item)
                      : ((item as Record<string, unknown>)[column.key] as React.ReactNode)}
                  </span>
                ))}
              </div>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  )
}

export function DataTable<T extends { id: string | number }>({
  columns,
  data,
  onRowClick,
  className,
  mobileFallback,
}: DataTableProps<T>) {
  const fallback =
    mobileFallback ?? (
      <DefaultMobileCards columns={columns} data={data} onRowClick={onRowClick} />
    )

  return (
    <AdaptiveDataView className={cn("overflow-hidden", className)} mobileFallback={fallback}>
      <table className="w-full min-w-[640px]">
        <thead>
          <tr className="border-b border-divide bg-[color:var(--g-surface-2)]">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "h-[var(--np-header-h)] px-3 py-0 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-divide">
          {data.map((item) => (
            <tr
              key={item.id}
              onClick={() => onRowClick?.(item)}
              className={cn(
                "h-[var(--np-row-h)] bg-[color:var(--g-surface-1)] transition-colors",
                onRowClick && "cursor-pointer hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn("px-3 py-0 text-sm text-foreground align-middle", column.className)}
                >
                  {column.render
                    ? column.render(item)
                    : ((item as Record<string, unknown>)[column.key] as React.ReactNode)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </AdaptiveDataView>
  )
}
