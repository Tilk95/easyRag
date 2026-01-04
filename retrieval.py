from __future__ import annotations

from typing import Dict, List, Optional

from store.sqlite import connect_db, init_db, search_fts as _search_fts, get_chunk as _get_chunk


def search_fts(db_path: str, q: str, top_k: int = 10, doc_type: Optional[str] = None, scope: Optional[str] = None) -> List[Dict]:
    conn = connect_db(db_path)
    init_db(conn)
    return _search_fts(conn, q=q, top_k=top_k, doc_type=doc_type, scope=scope)


def get_chunk(db_path: str, chunk_id: int) -> Dict:
    conn = connect_db(db_path)
    init_db(conn)
    return _get_chunk(conn, chunk_id)
