# Gravitre public-page and article publishing contract

Scope: public marketing pages, public documentation and Gravitre blog posts. Never add account, workspace, API, or staging URLs to the sitemap.

## Required at publication
- A single meaningful H1 and a distinct, corresponding browser title (rendered target 30-60 characters). Account for layout suffixes; use `title.absolute` only when appropriate.
- A self-referencing **absolute** canonical on every public page; normalize www and campaign parameters to the canonical URL.
- A 110-160-character human-written meta description, describing the actual content.
- One direct definition or answer near the opening where appropriate. Avoid boilerplate and repetitive structure.
- Real author attribution for article content, publication date, and real modification date only when edited. Do not invent credentials, citations, or editorial dates.
- Factual assertions link to independently verified primary sources. Aim for two independent sources when a factual article warrants it; do not cite sources that have not been read.
- Images include intrinsic dimensions, descriptive alt text, and optimized delivery (Next Image where compatible).
- Blog posts and public docs appear in /sitemap.xml. Static pages omit lastmod when none can be verified. Never use build time as publication time.
- Invalid routes must return an HTTP 404. Check this at runtime, including unknown /docs and /blog URLs.
- Duplicates must be resolved by a URL-level editorial decision: differentiated search intent or explicit permanent redirect. Never infer redirects only from matching titles.
- Short pages require editorial review, not meaningless padding to reach an arbitrary word count.
- Organization JSON-LD identifies Gravitre consistently; sameAs only for accounts verified as owned by the company.
- Article JSON-LD matches visible author, title and dates. Do not add unverified authors or fake review markup.

## Release evidence
1. Check the generated HTML and browser DOM for metadata, schema, H1, canonical and image layout.
2. Verify /sitemap.xml and /robots.txt return HTTP 200 and /missing-page-audit-probe returns HTTP 404.
3. Open a new blog post and check publication date, author, source URLs, metadata, and inclusion in the sitemap.
4. Run the SEO publishing CI guard and address its advisories for newly written content.
5. Ping IndexNow only after a public, verified URL is published and the domain ownership key has been configured. Never ping preview URLs.
6. Review Search Console indexing and organic clicks; do not promise rankings from markup changes.

Previously published items require an editorial inventory and approvals before merging, deleting or redirecting them. The build-time gate is intentionally advisory on word counts and source counts.
