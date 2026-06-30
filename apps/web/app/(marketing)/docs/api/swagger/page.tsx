export default function ApiSwaggerPage() {
  const specUrl = "/docs/api/openapi.json"

  return (
    <div className="min-h-screen bg-white">
      <section className="border-b border-zinc-200 bg-zinc-50/50 px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <h1 className="text-3xl font-semibold text-zinc-900">API reference (Swagger UI)</h1>
          <p className="mt-3 max-w-3xl text-zinc-600">
            Interactive explorer for the public Gravitre REST API. Internal admin routes are
            omitted from the published spec.
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            Raw spec:{" "}
            <a className="text-emerald-700 hover:underline" href={specUrl}>
              {specUrl}
            </a>
          </p>
        </div>
      </section>
      <iframe
        title="Gravitre API Swagger UI"
        src={`https://petstore.swagger.io/?url=${encodeURIComponent(`https://gravitre.app${specUrl}`)}`}
        className="h-[calc(100vh-180px)] w-full border-0"
      />
    </div>
  )
}
