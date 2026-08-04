from app.services.artifact_registry_service import get_artifact_registry_service
from app.services.chat_hosted_file_service import (
    markdown_to_csv_bytes,
    markdown_to_docx_bytes,
    markdown_to_simple_html,
    status_breakdown_chart_html,
    _minimal_pdf_bytes,
)
from app.services.conversational_execution_service import ExecutionResult


def test_markdown_to_simple_html_includes_headings_and_lists():
    html = markdown_to_simple_html("Brief", "# Brief\n\n- One\n- Two\n")
    assert "<h1>Brief</h1>" in html
    assert "<li>One</li>" in html


def test_markdown_table_to_csv():
    md = "| Name | Count |\n| --- | --- |\n| A | 1 |\n| B | 2 |\n"
    raw = markdown_to_csv_bytes(md)
    assert raw is not None
    text = raw.decode("utf-8")
    assert "Name,Count" in text.replace(" ", "")
    assert "A,1" in text.replace(" ", "")


def test_docx_and_pdf_bytes_non_empty():
    docx = markdown_to_docx_bytes("Title", "# Title\n\nHello world")
    pdf = _minimal_pdf_bytes("Title", "Hello world")
    assert docx[:2] == b"PK"
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100


def test_status_chart_html():
    html = status_breakdown_chart_html("Runs", {"completed": 3, "failed": 1})
    assert "<svg" in html
    assert "complete" in html  # axis labels truncated to 8 chars
    assert ">3<" in html


def test_artifact_registry_emits_hosted_file_chips():
    registry = get_artifact_registry_service()
    result = ExecutionResult(
        success=True,
        entity_type="document",
        entity_id="doc-1",
        title="Brief",
        body="Generated",
        structured={
            "format": "markdown",
            "title": "Brief",
            "content": "# Brief\nHello",
            "code": "# Brief\nHello",
            "previewHtml": "<html><body>Brief</body></html>",
            "hostedFiles": [
                {
                    "id": "1:md",
                    "filename": "brief.md",
                    "mime_type": "text/markdown",
                    "byte_size": 12,
                    "role": "markdown",
                    "download_url": "https://example.com/brief.md",
                    "durable": True,
                }
            ],
        },
    )
    artifacts = registry.build_artifacts(result)
    kinds = {row["kind"] for row in artifacts}
    assert "document" in kinds
    assert "hosted_file" in kinds
    hosted = next(row for row in artifacts if row["kind"] == "hosted_file")
    assert hosted["result_url"] == "https://example.com/brief.md"
    assert hosted["title"] == "brief.md"
