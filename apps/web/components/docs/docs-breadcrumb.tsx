import Link from "next/link"
import { ChevronRight } from "lucide-react"

export interface DocsBreadcrumbProps {
  category?: string
  title: string
}

export function DocsBreadcrumb({ category, title }: DocsBreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground">
      <Link href="/docs" className="transition-colors hover:text-foreground">
        Docs
      </Link>
      {category ? (
        <>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
          <span className="text-muted-foreground">{category}</span>
        </>
      ) : null}
      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
      <span className="truncate font-medium text-foreground">{title}</span>
    </nav>
  )
}
