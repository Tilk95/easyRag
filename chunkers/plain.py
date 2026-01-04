from __future__ import annotations

from typing import List

from chunkers.base import Chunker
from models import Document, Chunk


class PlainChunker(Chunker):
    """Chunker générique: découpe par paragraphes + taille max."""

    def __init__(self, max_chars: int = 4500):
        self.max_chars = max_chars

    def chunk(self, doc: Document) -> List[Chunk]:
        lines = doc.text.splitlines()
        chunks: List[Chunk] = []
        buf: List[str] = []
        start_line = 1
        idx = 0

        def flush(end_line: int) -> None:
            nonlocal idx, start_line, buf
            txt = "\n".join(buf).strip("\n")
            if txt.strip():
                chunks.append(
                    Chunk(
                        chunk_index=idx,
                        start_line=start_line,
                        end_line=end_line,
                        text=txt,
                        kind="block",
                        meta={"doc_type": doc.doc_type, "path": doc.path},
                    )
                )
                idx += 1
            buf = []
            start_line = end_line + 1

        for i, ln in enumerate(lines, start=1):
            buf.append(ln)
            if len("\n".join(buf)) >= self.max_chars:
                flush(i)
                continue
            if ln.strip() == "" and len(buf) >= 10:
                flush(i)

        if buf:
            flush(len(lines))

        return chunks
