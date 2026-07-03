import os

root = os.path.join(os.path.dirname(__file__), "..", "apps", "web", "app")
root = os.path.normpath(root)

content = '"use client"\n\nexport { default } from "@/components/gravitre/route-error"\n'

for dirpath, _, files in os.walk(root):
    if "error.tsx" not in files:
        continue
    path = os.path.join(dirpath, "error.tsx")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(path)
