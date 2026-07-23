#!/usr/bin/env python3
"""HTTP link checker for deployed Gravitre marketing/app surfaces.

Crawls a live deployment starting from the homepage, follows internal links found
in fetched HTML (<a href> — includes Next.js Link output), and reports status codes,
non-empty body checks, and metadata regressions.

Usage:
  python scripts/check-deployed-links.py
  python scripts/check-deployed-links.py --base-url https://gravitre.app --max-pages 200
  python scripts/check-deployed-links.py --base-url http://localhost:3000 --json report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

DEFAULT_BASE_URL = "https://gravitre.app"
HOMEPAGE_TITLE = "Gravitre — AI operations with GIBE"
USER_AGENT = "GravitreLinkChecker/1.0 (+https://gravitre.app)"

# Known regressions from manual QA — checked before crawl begins.
KNOWN_ASSERTIONS: list[dict[str, Any]] = [
    {
        "url": "/support/getting-started",
        "max_status": 399,
        "min_text_len": 80,
        "note": "Support category link was 404",
    },
    {
        "url": "/guides/create-your-first-ai-agent",
        "max_status": 399,
        "min_text_len": 80,
        "note": "Featured guide card was 404",
    },
    {
        "url": "/docs/guides/how-to-create-your-first-agent",
        "max_status": 399,
        "min_text_len": 120,
        "must_not_contain": ["noindex"],
        "note": "Popular article slug was empty/noindex",
    },
    {
        "url": "/docs/sdk/node",
        "max_status": 399,
        "min_text_len": 120,
        "note": "SDK stub redirected to REST quickstart",
    },
]

METADATA_PAGES: list[dict[str, str]] = [
    {"url": "/api", "expected_title_fragment": "API"},
    {"url": "/support", "expected_title_fragment": "Support"},
    {"url": "/changelog", "expected_title_fragment": "Changelog"},
]

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")
SKIP_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".json",
    ".xml",
    ".woff",
    ".woff2",
    ".ttf",
    ".mp4",
    ".webm",
)


@dataclass
class FetchResult:
    url: str
    status: int
    final_url: str
    content_type: str
    body: str
    text_len: int
    title: str
    og_title: str
    robots: str
    error: str | None = None


@dataclass
class LinkEdge:
    target: str
    source: str


@dataclass
class CrawlReport:
    base_url: str
    pages: dict[str, FetchResult] = field(default_factory=dict)
    edges: list[LinkEdge] = field(default_factory=list)
    assertion_failures: list[str] = field(default_factory=list)
    metadata_failures: list[str] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def normalize_url(base: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith("#") or href.startswith(SKIP_SCHEMES):
        return None
    joined = urllib.parse.urljoin(base, href)
    parsed = urllib.parse.urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None
    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return None
    # Drop query/hash for crawl identity; keep path only for same-site pages.
    clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return clean


def same_origin(base: str, url: str) -> bool:
    base_host = urllib.parse.urlparse(base).netloc.lower()
    url_host = urllib.parse.urlparse(url).netloc.lower()
    return base_host == url_host


def strip_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_meta(html: str, *, prop: str | None = None, name: str | None = None) -> str:
    if prop:
        pattern = rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']*)["\']'
        alt = rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']{re.escape(prop)}["\']'
    else:
        assert name is not None
        pattern = rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']'
        alt = rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(name)}["\']'
    for rx in (pattern, alt):
        match = re.search(rx, html, flags=re.I)
        if match:
            return match.group(1).strip()
    return ""


def extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def fetch_url(url: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body_bytes = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            body = body_bytes.decode(charset, errors="replace")
            final_url = response.geturl()
            status = getattr(response, "status", 200) or 200
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read() if exc.fp else b""
        body = body_bytes.decode("utf-8", errors="replace")
        return FetchResult(
            url=url,
            status=exc.code,
            final_url=exc.geturl(),
            content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
            body=body,
            text_len=len(strip_text(body)),
            title=extract_title(body),
            og_title=extract_meta(body, prop="og:title"),
            robots=extract_meta(body, name="robots"),
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(
            url=url,
            status=0,
            final_url=url,
            content_type="",
            body="",
            text_len=0,
            title="",
            og_title="",
            robots="",
            error=str(exc),
        )

    text = strip_text(body)
    return FetchResult(
        url=url,
        status=status,
        final_url=final_url,
        content_type=content_type,
        body=body,
        text_len=len(text),
        title=extract_title(body),
        og_title=extract_meta(body, prop="og:title"),
        robots=extract_meta(body, name="robots"),
    )


def evaluate_assertions(base_url: str, timeout: float) -> tuple[list[str], dict[str, FetchResult]]:
    failures: list[str] = []
    fetched: dict[str, FetchResult] = {}
    for spec in KNOWN_ASSERTIONS:
        path = spec["url"]
        url = urllib.parse.urljoin(base_url, path)
        result = fetch_url(url, timeout)
        fetched[url] = result
        ok = True
        if result.status == 0 or result.status > spec.get("max_status", 399):
            failures.append(f"{path} -> status {result.status} ({spec.get('note', '')})")
            ok = False
        if result.text_len < spec.get("min_text_len", 1):
            failures.append(f"{path} -> empty body (text_len={result.text_len}) ({spec.get('note', '')})")
            ok = False
        for needle in spec.get("must_not_contain", []):
            hay = f"{result.body} {result.robots}".lower()
            if needle.lower() in hay:
                failures.append(f"{path} -> contains forbidden {needle!r} ({spec.get('note', '')})")
                ok = False
        if ok:
            print(f"PASS assertion {path} status={result.status} text_len={result.text_len}")
        else:
            print(f"FAIL assertion {path} status={result.status} text_len={result.text_len}")
    return failures, fetched


def evaluate_metadata(base_url: str, timeout: float) -> tuple[list[str], dict[str, FetchResult]]:
    failures: list[str] = []
    fetched: dict[str, FetchResult] = {}
    for spec in METADATA_PAGES:
        path = spec["url"]
        url = urllib.parse.urljoin(base_url, path)
        result = fetch_url(url, timeout)
        fetched[url] = result
        fragment = spec["expected_title_fragment"]
        title = result.title
        og = result.og_title
        page_failures: list[str] = []
        if result.status >= 400:
            page_failures.append(f"{path} metadata check blocked by HTTP {result.status}")
        elif title == HOMEPAGE_TITLE:
            page_failures.append(f"{path} <title> still homepage default: {title!r}")
        elif og == HOMEPAGE_TITLE:
            page_failures.append(f"{path} og:title still homepage default: {og!r}")
        elif fragment.lower() not in title.lower() and fragment.lower() not in og.lower():
            page_failures.append(
                f"{path} missing expected title fragment {fragment!r} (title={title!r}, og:title={og!r})"
            )

        if page_failures:
            failures.extend(page_failures)
            for line in page_failures:
                print(f"FAIL metadata {line}")
        else:
            print(f"PASS metadata {path} title={title!r} og:title={og!r}")
    return failures, fetched


def crawl(base_url: str, *, max_pages: int, timeout: float) -> CrawlReport:
    report = CrawlReport(base_url=base_url.rstrip("/"))
    start = report.base_url + "/"
    queue: deque[str] = deque([start])
    seen: set[str] = set()

    print(f"Crawling {report.base_url} (max_pages={max_pages})")
    while queue and len(report.pages) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        if url in report.pages:
            continue

        result = fetch_url(url, timeout)
        report.pages[url] = result
        path = urllib.parse.urlparse(url).path or "/"
        print(f"  [{result.status}] {path} text_len={result.text_len}")

        if result.status >= 400 or result.status == 0:
            report.broken.append(url)
        elif result.text_len < 40 and "text/html" in result.content_type:
            report.empty.append(url)

        if "text/html" not in result.content_type and result.content_type:
            continue

        parser = LinkExtractor()
        try:
            parser.feed(result.body)
        except Exception:  # noqa: BLE001
            continue

        for href in parser.links:
            normalized = normalize_url(url, href)
            if not normalized or not same_origin(report.base_url, normalized):
                continue
            report.edges.append(LinkEdge(target=normalized, source=url))
            if normalized not in seen:
                queue.append(normalized)

    return report


def print_report(report: CrawlReport) -> None:
    print("\n=== Known assertion failures ===")
    if report.assertion_failures:
        for line in report.assertion_failures:
            print(f"  - {line}")
    else:
        print("  (none)")

    print("\n=== Metadata failures ===")
    if report.metadata_failures:
        for line in report.metadata_failures:
            print(f"  - {line}")
    else:
        print("  (none)")

    print("\n=== Crawl broken URLs (status >= 400) ===")
    for url in sorted(set(report.broken)):
        result = report.pages.get(url)
        status = result.status if result else "?"
        sources = sorted({edge.source for edge in report.edges if edge.target == url})
        source = sources[0] if sources else "(seed/direct)"
        print(f"  {urllib.parse.urlparse(url).path} -> {status} (from {urllib.parse.urlparse(source).path})")

    print("\n=== Crawl empty HTML pages (text_len < 40) ===")
    for url in sorted(set(report.empty)):
        result = report.pages.get(url)
        text_len = result.text_len if result else 0
        sources = sorted({edge.source for edge in report.edges if edge.target == url})
        source = sources[0] if sources else "(seed/direct)"
        print(f"  {urllib.parse.urlparse(url).path} -> text_len={text_len} (from {urllib.parse.urlparse(source).path})")

    print(f"\nPages fetched: {len(report.pages)} | Edges: {len(report.edges)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl deployed site links over HTTP")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Deployment origin")
    parser.add_argument("--max-pages", type=int, default=250, help="Maximum pages to crawl")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--json", dest="json_path", help="Write JSON report to path")
    parser.add_argument("--skip-crawl", action="store_true", help="Only run known/metadata checks")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    report = CrawlReport(base_url=base)

    print(f"Target: {base}\n--- Known assertions ---")
    report.assertion_failures, assertion_pages = evaluate_assertions(base, args.timeout)
    report.pages.update(assertion_pages)

    print("\n--- Metadata checks ---")
    report.metadata_failures, metadata_pages = evaluate_metadata(base, args.timeout)
    report.pages.update(metadata_pages)

    if not args.skip_crawl:
        print("\n--- Crawl ---")
        crawl_report = crawl(base, max_pages=args.max_pages, timeout=args.timeout)
        report.pages.update(crawl_report.pages)
        report.edges.extend(crawl_report.edges)
        report.broken.extend(crawl_report.broken)
        report.empty.extend(crawl_report.empty)

    print_report(report)

    if args.json_path:
        payload = {
            "base_url": report.base_url,
            "assertion_failures": report.assertion_failures,
            "metadata_failures": report.metadata_failures,
            "broken": [
                {
                    "url": url,
                    "path": urllib.parse.urlparse(url).path,
                    "status": report.pages[url].status if url in report.pages else None,
                    "sources": sorted({edge.source for edge in report.edges if edge.target == url}),
                }
                for url in sorted(set(report.broken))
            ],
            "empty": [
                {
                    "url": url,
                    "path": urllib.parse.urlparse(url).path,
                    "text_len": report.pages[url].text_len if url in report.pages else 0,
                    "sources": sorted({edge.source for edge in report.edges if edge.target == url}),
                }
                for url in sorted(set(report.empty))
            ],
            "pages": {
                url: {
                    "status": result.status,
                    "text_len": result.text_len,
                    "title": result.title,
                    "og_title": result.og_title,
                }
                for url, result in report.pages.items()
            },
        }
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nWrote JSON report to {args.json_path}")

    failed = bool(report.assertion_failures or report.metadata_failures or report.broken or report.empty)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
