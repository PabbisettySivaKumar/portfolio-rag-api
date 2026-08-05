import re

_HEADER_RE = re.compile(r"^#{1,6}\s")


def _split_sections(text: str) -> list[str]:
    """Split markdown into sections that each begin at a header line and run
    until the next header. Any preamble before the first header is its own
    section. This keeps a heading attached to the content it describes instead
    of slicing through it at an arbitrary character offset.
    """
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        if _HEADER_RE.match(line) and current:
            sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("".join(current))
    return [section.strip() for section in sections if section.strip()]


def _hard_split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fixed-width fallback for a single section larger than max_chars."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Chunk markdown along its structure. Sections are packed together up to
    max_chars so small sections share a chunk, section boundaries are respected,
    and any oversized section falls back to a fixed-width split with overlap.
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    buffer = ""

    for section in _split_sections(text):
        if len(section) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_hard_split(section, max_chars, overlap))
        elif not buffer:
            buffer = section
        elif len(buffer) + 2 + len(section) <= max_chars:
            buffer = f"{buffer}\n\n{section}"
        else:
            chunks.append(buffer)
            buffer = section

    if buffer:
        chunks.append(buffer)

    return chunks
