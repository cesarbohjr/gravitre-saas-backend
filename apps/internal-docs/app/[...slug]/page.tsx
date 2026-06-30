import Link from "next/link"
import { compileMDX } from "next-mdx-remote/rsc"
import { notFound } from "next/navigation"
import remarkGfm from "remark-gfm"

import { getInternalDoc, getInternalDocSlugs } from "@/lib/load-internal-docs"

export async function generateStaticParams() {
  return getInternalDocSlugs().map((slug) => ({ slug: slug.split("/") }))
}

export default async function InternalDocPage({
  params,
}: {
  params: Promise<{ slug: string[] }>
}) {
  const { slug } = await params
  const doc = getInternalDoc(slug.join("/"))
  if (!doc) notFound()

  const { content } = await compileMDX({
    source: doc.content,
    options: { mdxOptions: { remarkPlugins: [remarkGfm] } },
  })

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
        ← Internal docs home
      </Link>
      <p className="mt-4 text-xs font-medium uppercase tracking-wide text-amber-700">
        Internal · {doc.category}
      </p>
      <h1 className="mt-2 text-3xl font-semibold text-zinc-900">{doc.title}</h1>
      <p className="mt-3 text-zinc-600">{doc.description}</p>
      <article className="prose prose-zinc mt-10 max-w-none">{content}</article>
    </main>
  )
}
