from __future__ import annotations

import re
from typing import List, Optional, Tuple

from chunkers.base import Chunker
from models import Document, Chunk

_LABEL_RE = re.compile(r"^\s*\$[A-Za-z0-9_]+:\s*$")
_SECTION_RE = re.compile(r"^\s*\$!\s*[-=]{3,}.*$|^\s*\$!\s*(SECTION|PHASE)\b.*$", re.IGNORECASE)
_PHASE_RE = re.compile(
    r"^\s*\$(\s+)?("
    r"SET\s+(NOON|ON|VERIFY|DEFAULT|MESSAGE)|"
    r"ON\s+ERROR|"
    r"EXIT\b|STOP\b|LOGOUT\b|"
    r"RUN\b|MCR\b|PIPE\b|SUBMIT\b|@"
    r")\b",
    re.IGNORECASE,
)


class DclChunker(Chunker):
    """Chunker DCL .COM : labels/sections/ancres de phase + fusion/split."""

    def __init__(self, min_lines: int = 8, max_lines: int = 60, max_chars: int = 4500):
        self.min_lines = min_lines
        self.max_lines = max_lines
        self.max_chars = max_chars

    def chunk(self, doc: Document) -> List[Chunk]:
        lines = doc.text.splitlines()
        n = len(lines)

        def is_delim(line: str) -> Optional[str]:
            if _LABEL_RE.match(line):
                return "label"
            if _SECTION_RE.match(line):
                return "section"
            if _PHASE_RE.match(line):
                return "block"
            return None

        segments: List[Tuple[int, int, str]] = []
        start = 0
        kind = "block"
        i = 0
        while i < n:
            k = is_delim(lines[i])
            if k and i != start:
                segments.append((start, i - 1, kind))
                start = i
                kind = k
            if lines[i].strip() == "" and (i - start + 1) >= max(self.min_lines, 12):
                segments.append((start, i, kind))
                start = i + 1
                kind = "block"
            i += 1
        if start < n:
            segments.append((start, n - 1, kind))

        chunks: List[Chunk] = []
        for (s, e, k) in segments:
            txt = "\n".join(lines[s:e + 1]).strip("\n")
            if txt.strip():
                chunks.append(
                    Chunk(
                        chunk_index=len(chunks),
                        start_line=s + 1,
                        end_line=e + 1,
                        text=txt,
                        kind=k,
                        meta={"doc_type": doc.doc_type, "path": doc.path},
                    )
                )

        # merge small chunks
        merged: List[Chunk] = []
        for ch in chunks:
            if not merged:
                merged.append(ch)
                continue
            prev = merged[-1]
            prev_lines = prev.end_line - prev.start_line + 1
            ch_lines = ch.end_line - ch.start_line + 1
            if ch_lines < self.min_lines or prev_lines < self.min_lines:
                merged[-1] = Chunk(
                    chunk_index=prev.chunk_index,
                    start_line=prev.start_line,
                    end_line=ch.end_line,
                    text=prev.text + "\n" + ch.text,
                    kind=prev.kind,
                    meta=prev.meta,
                )
            else:
                merged.append(ch)

        # split big chunks
        final: List[Chunk] = []
        for ch in merged:
            ch_lines = ch.end_line - ch.start_line + 1
            if ch_lines <= self.max_lines and len(ch.text) <= self.max_chars:
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
                continue

            all_lines = ch.text.splitlines()
            base_start = ch.start_line
            idx = 0
            while idx < len(all_lines):
                part = all_lines[idx: idx + self.max_lines]
                part_txt = "\n".join(part)
                part_start = base_start + idx
                part_end = part_start + len(part) - 1
                final.append(
                    Chunk(
                        chunk_index=len(final),
                        start_line=part_start,
                        end_line=part_end,
                        text=part_txt,
                        kind=ch.kind,
                        meta=ch.meta,
                    )
                )
                idx += self.max_lines

        return final
