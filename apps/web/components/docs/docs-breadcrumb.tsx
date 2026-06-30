import Link from "next/link"
import { ChevronRight } from "lucide-react"

export interface DocsBreadcrumbProps {
  category?: string
  title: string
}

export function DocsBreadcrumb({ category, title }: DocsBreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-sm text-zinc-500">
      <Link href="/docs" className="transition-colors hover:text-zinc-900">
        Docs
      </Link>
      {category ? (
        <>
          <ChevronRight className="h-3.5 w-3.5 text-zinc-300" />
          <span className="text-zinc-500">{category}</span>
        </>
      ) : null}
      <ChevronRight className="h-3.5 w-3.5 text-zinc-300" />
      <span className="truncate font-medium text-zinc-700">{title}</span>
    </nav>
  )
}
