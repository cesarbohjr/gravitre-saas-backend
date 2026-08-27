#!/usr/bin/env python3
import re
import sys

import httpx

html = httpx.get("https://gravitre.app/ai", timeout=30, follow_redirects=True).text
chunks = re.findall(r"/_next/static/[^\"']+", html)
print("url", httpx.get("https://gravitre.app/ai", timeout=30, follow_redirects=True).url)
for c in chunks[:25]:
    print(c)
