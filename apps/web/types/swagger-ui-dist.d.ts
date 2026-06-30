declare module "swagger-ui-dist/swagger-ui-es-bundle.js" {
  type SwaggerUIConfig = {
    domNode?: HTMLElement | null
    url?: string
    spec?: Record<string, unknown>
    deepLinking?: boolean
    docExpansion?: "list" | "full" | "none"
    defaultModelsExpandDepth?: number
    tryItOutEnabled?: boolean
    persistAuthorization?: boolean
    syntaxHighlight?: { theme?: string } | boolean
    presets?: unknown[]
    plugins?: unknown[]
    [key: string]: unknown
  }

  const SwaggerUIBundle: (config: SwaggerUIConfig) => unknown
  export default SwaggerUIBundle
}

declare module "swagger-ui-dist/swagger-ui.css"
