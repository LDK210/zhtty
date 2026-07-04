from __future__ import annotations

from pathlib import Path


class TextExtractionError(RuntimeError):
    pass


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(path)
    elif suffix == ".docx":
        text = _extract_docx(path)
    else:
        raise TextExtractionError("Only PDF and DOCX files are supported.")

    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        raise TextExtractionError("No text could be extracted from this resume.")
    return cleaned


def _extract_pdf(path: Path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        try:
            import fitz

            doc = fitz.open(path)
            return "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            raise TextExtractionError(f"Failed to extract PDF text: {exc}") from exc


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document

        document = Document(path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise TextExtractionError(f"Failed to extract DOCX text: {exc}") from exc
