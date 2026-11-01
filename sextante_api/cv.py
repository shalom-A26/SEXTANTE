"""Extract plain text from an uploaded CV, in memory only.

The CV is never written to disk, logged or stored: it is parsed from the
request bytes, scored, and discarded with the response (data-ethics rule).
"""

from __future__ import annotations

import io

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 60_000


class CvError(ValueError):
    """The upload cannot be read as a CV."""


def extract_text(filename: str, content: bytes) -> str:
    if not content:
        raise CvError("El archivo está vacío.")
    if len(content) > MAX_BYTES:
        raise CvError("El archivo supera 5 MB.")
    name = (filename or "").casefold()
    if name.endswith(".pdf") or content[:5] == b"%PDF-":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # malformed PDFs raise many exception types
            raise CvError("No se pudo leer el PDF.") from exc
    elif name.endswith(".docx"):
        from docx import Document

        try:
            document = Document(io.BytesIO(content))
        except Exception as exc:
            raise CvError("No se pudo leer el DOCX.") from exc
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    elif name.endswith((".txt", ".md")) or not name:
        text = content.decode("utf-8", errors="replace")
    else:
        raise CvError("Formato no soportado: usa PDF, DOCX o TXT.")
    text = text.strip()
    if len(text) < 30:
        raise CvError("No se encontró texto suficiente en el CV (¿es un PDF escaneado?).")
    return text[:MAX_CHARS]
