"""Agency staging review uses seed command's read-only mode."""
from unittest.mock import patch

from scripts.seed_marketplace import main


def test_agency_review_without_database_or_settings(capsys):
    with patch("sys.argv", ["seed_marketplace.py", "--agency-review"]):
        result = main()
    output = capsys.readouterr().out
    assert result == 0
    assert '"publication_enabled": false' in output
    assert '"preview_only": true' in output


def test_agency_review_cannot_backfill(capsys):
    with patch("sys.argv", ["seed_marketplace.py", "--agency-review", "--backfill-legacy"]):
        assert main() == 2
    assert "cannot backfill" in capsys.readouterr().err
