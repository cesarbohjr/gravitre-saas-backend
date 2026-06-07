"""Minimal HTML helpers — clean layout aligned with Gravitre's dark UI."""
from __future__ import annotations

from html import escape


BASE_STYLE = """
  :root { color-scheme: dark; }
  body { font-family: ui-sans-serif, system-ui, sans-serif; background: #0a0a0b; color: #e4e4e7; margin: 0; }
  .wrap { max-width: 880px; margin: 0 auto; padding: 2rem 1.25rem; }
  h1, h2 { font-weight: 600; letter-spacing: -0.02em; }
  p, li { color: #a1a1aa; line-height: 1.6; }
  a { color: #a78bfa; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .card { background: #141416; border: 1px solid #27272a; border-radius: 12px; padding: 1.25rem; margin: 1rem 0; }
  .btn { display: inline-block; background: #7c3aed; color: #fff; padding: 0.6rem 1rem; border-radius: 8px; border: 0; cursor: pointer; font-weight: 500; }
  .btn.secondary { background: #27272a; color: #e4e4e7; }
  label { display: block; font-size: 0.875rem; margin-bottom: 0.35rem; color: #d4d4d8; }
  input, textarea, select { width: 100%; padding: 0.55rem 0.65rem; border-radius: 8px; border: 1px solid #3f3f46; background: #09090b; color: #fafafa; margin-bottom: 0.85rem; }
  .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
  .badge { display: inline-block; font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 999px; background: #27272a; color: #d4d4d8; }
  .badge.ok { background: #14532d; color: #bbf7d0; }
  .badge.warn { background: #713f12; color: #fde68a; }
  .error { background: #450a0a; border: 1px solid #7f1d1d; color: #fecaca; padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0; }
  code { font-family: ui-monospace, monospace; font-size: 0.85em; }
"""


def page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · Stripe Connect Sample</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
  <div class="wrap">
    <p><a href="/samples/stripe-connect">← Sample home</a></p>
    {body}
  </div>
</body>
</html>"""
