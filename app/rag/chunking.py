def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
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
