from __future__ import annotations

import re
from typing import List

from chunkers.base import Chunker
from chunkers.plain import PlainChunker
from models import Document, Chunk

_FUNC_RE = re.compile(
    r"""^\s*(?:[A-Za-z_][\w\s\*\(\)]*?)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{""",
    re.MULTILINE,
)


class CLikeChunker(Chunker):
    """Chunker C/H : découpe par fonctions détectées via regex, fallback plain."""

    def __init__(self, max_chars: int = 6500):
        self.max_chars = max_chars
        self.plain = PlainChunker(max_chars=max_chars)

    def chunk(self, doc: Document) -> List[Chunk]:
        text = doc.text
        matches = list(_FUNC_RE.finditer(text))
        if not matches:
            return self.plain.chunk(doc)

        line_starts = [0]
        for m in re.finditer(r"\n", text):
            line_starts.append(m.end())

        def char_to_line(pos: int) -> int:
            lo, hi = 0, len(line_starts) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if line_starts[mid] <= pos:
                    lo = mid + 1
                else:
                    hi = mid - 1
            return hi + 1

        chunks: List[Chunk] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip("\n")
            if not body.strip():
                continue
            fn = m.group(1)
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    start_line=char_to_line(start),
                    end_line=char_to_line(end),
                    text=body,
                    kind="function",
                    meta={"doc_type": doc.doc_type, "path": doc.path, "function": fn},
                )
            )

        final: List[Chunk] = []
        for ch in chunks:
            if len(ch.text) <= self.max_chars:
                final.append(
                    Chunk(
                        chunk_index=len(final),
                        start_line=ch.start_line,
                        end_line=ch.end_line,
                        text=ch.text,
                        kind=ch.kind,
                        meta=ch.meta,
                    )
                )
            else:
                subdoc = Document(doc.doc_id, doc.path, doc.rel_folder, doc.doc_type, ch.text, doc.meta)
                subs = self.plain.chunk(subdoc)
                for sub in subs:
                    final.append(
                        Chunk(
                            chunk_index=len(final),
                            start_line=ch.start_line + (sub.start_line - 1),
                            end_line=ch.start_line + (sub.end_line - 1),
                            text=sub.text,
                            kind="function_part",
                            meta=ch.meta,
                        )
                    )
        return final
