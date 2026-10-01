from app.capabilities.license_detection import detect_bundle_license


def test_detects_mit_license_file() -> None:
    detected = detect_bundle_license(
        {"LICENSE": "MIT License\nPermission is hereby granted, free of charge, to any person obtaining a copy of the Software."}
    )
    assert detected == "MIT"


def test_restrictive_license_file_is_not_treated_as_open() -> None:
    detected = detect_bundle_license({"LICENSE.txt": "All rights reserved. No redistribution."})
    assert detected and detected.startswith("Proprietary")
