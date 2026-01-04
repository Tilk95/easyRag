from __future__ import annotations

import re
from typing import List

from chunkers.base import Chunker
from chunkers.plain import PlainChunker
from models import Document, Chunk

_STMT_END_RE = re.compile(r";\s*$", re.MULTILINE)
_KEYWORD_RE = re.compile(r"^\s*(SELECT|UPDATE|INSERT|DELETE|CREATE|DROP|ALTER|DECLARE)\b", re.IGNORECASE)


class SQLModChunker(Chunker):
    """Chunker SQL/SQLMOD : découpe par statements (;) + mots-clés, fallback plain."""

    def __init__(self, max_lines: int = 120):
        self.max_lines = max_lines
        self.plain = PlainChunker(max_chars=6500)

    def chunk(self, doc: Document) -> List[Chunk]:
        lines = doc.text.splitlines()
        if not lines:
            return []

        chunks: List[Chunk] = []
        buf: List[str] = []
        start_line = 1
        kind = "query"

        def flush(end_line: int) -> None:
            nonlocal buf, start_line
            txt = "\n".join(buf).strip("\n")
            if txt.strip():
                chunks.append(
                    Chunk(
                        chunk_index=len(chunks),
                        start_line=start_line,
                        end_line=end_line,
                        text=txt,
                        kind=kind,
                        meta={"doc_type": doc.doc_type, "path": doc.path},
                    )
                )
            buf = []
            start_line = end_line + 1

        for i, ln in enumerate(lines, start=1):
            if _KEYWORD_RE.match(ln) and buf:
                flush(i - 1)
            buf.append(ln)
            if _STMT_END_RE.search(ln) or (i - start_line + 1) >= self.max_lines:
                flush(i)

        if buf:
            flush(len(lines))

        if len(chunks) <= 1 and len(doc.text) > 6500:
            return self.plain.chunk(doc)
        return chunks
