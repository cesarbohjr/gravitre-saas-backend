from pathlib import Path
import re

p = Path("backend/app/knowledge_fabric/registry.py")
lines = p.read_text(encoding="utf-8").splitlines(True)
out = []
for i, line in enumerate(lines):
    out.append(line)
    if 'legal_review_status="verified_live"' in line:
        window = "".join(lines[i : i + 6])
        if "licence_verified" not in window:
            indent = re.match(r"^(\s*)", line).group(1)
            out.append(f"{indent}licence_verified=True,\n")
p.write_text("".join(out), encoding="utf-8")
print("count", p.read_text(encoding="utf-8").count("licence_verified=True"))
