from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Document:
    doc_id: str
    path: str
    rel_folder: str
    doc_type: str  # dcl | c | sqlmod | text
    text: str
    meta: Dict[str, str]


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    start_line: int
    end_line: int
    text: str
    kind: str
    meta: Dict[str, str]
