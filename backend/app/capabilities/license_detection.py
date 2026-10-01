"""Conservative license detection for imported portable capability bundles."""
from __future__ import annotations

from pathlib import PurePosixPath

_LICENSE_NAMES = {"license", "license.txt", "license.md", "copying", "copying.txt"}


def detect_bundle_license(files: dict[str, str]) -> str | None:
    candidates: list[str] = []
    for path, content in files.items():
        if PurePosixPath(path).name.lower() in _LICENSE_NAMES:
            candidates.append(str(content or ""))
    if not candidates:
        return None
    text = "\n".join(candidates).lower()
    if "apache license" in text and "version 2.0" in text:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in text and "the software" in text:
        return "MIT"
    if "gnu affero general public license" in text:
        return "AGPL-3.0"
    if "gnu lesser general public license" in text:
        return "LGPL-3.0"
    if "gnu general public license" in text:
        return "GPL-3.0"
    if "mozilla public license" in text and "2.0" in text:
        return "MPL-2.0"
    if "creative commons attribution 4.0" in text:
        return "CC-BY-4.0"
    if "all rights reserved" in text or "no redistribution" in text:
        return "Proprietary - redistribution restricted"
    return None
