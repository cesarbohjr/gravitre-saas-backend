import Link from "next/link"

import { listInternalDocs } from "@/lib/load-internal-docs"

export default function InternalDocsHome() {
  const docs = listInternalDocs()
  const byCategory = new Map<string, typeof docs>()

  for (const doc of docs) {
    const list = byCategory.get(doc.category) ?? []
    list.push(doc)
    byCategory.set(doc.category, list)
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-3xl font-semibold text-zinc-900">Gravitre internal docs</h1>
      <p className="mt-3 text-zinc-600">
        Private engineering documentation. Not for customer distribution.
      </p>

      <div className="mt-10 space-y-8">
        {Array.from(byCategory.entries()).map(([category, items]) => (
          <section key={category}>
            <h2 className="text-lg font-medium text-zinc-900">{category}</h2>
            <ul className="mt-3 space-y-2">
              {items.map((doc) => (
                <li key={doc.slug}>
                  <Link
                    href={`/${doc.slug}`}
                    className="text-emerald-700 hover:underline"
                  >
                    {doc.title}
                  </Link>
                  <p className="text-sm text-zinc-500">{doc.description}</p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </main>
  )
}
