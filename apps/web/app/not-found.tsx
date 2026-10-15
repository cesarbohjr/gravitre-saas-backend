import Link from "next/link"

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-2xl flex-col items-center justify-center px-6 py-16 text-center">
      <h1 className="text-4xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-4 text-base text-muted-foreground">
        The page may have moved or the address may be incorrect.
      </p>
      <Link className="mt-8 rounded-md bg-primary px-5 py-3 text-sm font-medium text-primary-foreground" href="/">
        Return to Gravitre
      </Link>
    </main>
  )
}
