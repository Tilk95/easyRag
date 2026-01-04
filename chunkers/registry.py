from __future__ import annotations

from typing import Dict

from chunkers.base import Chunker
from chunkers.plain import PlainChunker
from chunkers.dcl import DclChunker
from chunkers.c_like import CLikeChunker
from chunkers.sqlmod import SQLModChunker


class ChunkerRegistry:
    def __init__(self):
        self._by_type: Dict[str, Chunker] = {}

    def register(self, doc_type: str, chunker: Chunker) -> None:
        self._by_type[doc_type] = chunker

    def resolve(self, doc_type: str) -> Chunker:
        return self._by_type.get(doc_type) or self._by_type["text"]


def default_registry() -> ChunkerRegistry:
    reg = ChunkerRegistry()
    reg.register("text", PlainChunker(max_chars=4500))
    reg.register("dcl", DclChunker())
    reg.register("c", CLikeChunker())
    reg.register("sqlmod", SQLModChunker())
    return reg
