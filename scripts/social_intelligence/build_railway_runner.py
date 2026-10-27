"""Bundle the tested private runner and a clean, fixed synthetic prompt bundle."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(bundle: dict) -> str:
    if bundle.get("source_dirty") is not False or bundle.get("data_scope") != "fixed_synthetic_only":
        raise ValueError("A clean synthetic bundle is required")
    if len(bundle["profiles"]) != 40 or len(bundle["cases"]) != 26:
        raise ValueError("Expected all 520 paired evaluations")
    sources = [ROOT / name for name in ("durable_results.ts", "evaluator.ts", "railway_runner.ts")]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    compressed = base64.b64encode(gzip.compress(json.dumps(bundle, ensure_ascii=True).encode(), mtime=0)).decode()
    parts = ["// Tested runner source SHA256: " + json.dumps(hashes), "import {gunzipSync} from 'node:zlib';"]
    for source in sources:
        text = source.read_text()
        text = "\n".join(line for line in text.splitlines() if not (line.startswith("import ") and "'./" in line))
        text = text.replace("export ", "")
        text = text.replace("const bundle=JSON.parse(await Bun.file(process.argv[2]).text());", "const bundle=JSON.parse(gunzipSync(Buffer.from('" + compressed + "','base64')).toString('utf8'));")
        parts.append(text)
    return "\n".join(parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code = build(json.loads(args.bundle.read_text()))
    args.output.write_text(code)
    print(json.dumps({"bytes": len(code.encode()), "sha256": hashlib.sha256(code.encode()).hexdigest()}))
