from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from models import Document, Chunk


class Chunker(ABC):
    @abstractmethod
    def chunk(self, doc: Document) -> List[Chunk]:
        raise NotImplementedError
