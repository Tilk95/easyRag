from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional

from models import Document, Chunk

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  rel_folder TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  mtime INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  meta_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_type_folder ON documents(doc_type, rel_folder);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  doc_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  start_line INTEGER,
  end_line INTEGER,
  text TEXT NOT NULL,
  kind TEXT NOT NULL,
  meta_json TEXT,
  FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id, chunk_index);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
USING fts5(
  text,
  chunk_id UNINDEXED,
  doc_id UNINDEXED,
  path UNINDEXED,
  doc_type UNINDEXED,
  rel_folder UNINDEXED
);
"""


def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "fts5" in msg or "no such module" in msg:
            raise RuntimeError("SQLite FTS5 indisponible. Utilisez une distribution Python/SQLite incluant FTS5.") from e
        raise


def upsert_document(conn: sqlite3.Connection, doc: Document, mtime: int, file_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO documents(id, path, rel_folder, doc_type, mtime, sha256, meta_json)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          path=excluded.path,
          rel_folder=excluded.rel_folder,
          doc_type=excluded.doc_type,
          mtime=excluded.mtime,
          sha256=excluded.sha256,
          meta_json=excluded.meta_json;
        """,
        (doc.doc_id, doc.path, doc.rel_folder, doc.doc_type, mtime, file_hash, json.dumps(doc.meta, ensure_ascii=False)),
    )


def should_reindex(conn: sqlite3.Connection, doc_id: str, file_hash: str) -> bool:
    row = conn.execute("SELECT sha256 FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        return True
    return row["sha256"] != file_hash


def replace_chunks(conn: sqlite3.Connection, doc: Document, chunks: List[Chunk]) -> None:
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc.doc_id,))
    conn.execute("DELETE FROM chunks_fts WHERE doc_id=?", (doc.doc_id,))

    for ch in chunks:
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_index, start_line, end_line, text, kind, meta_json) VALUES(?, ?, ?, ?, ?, ?, ?)",
            (doc.doc_id, ch.chunk_index, ch.start_line, ch.end_line, ch.text, ch.kind, json.dumps(ch.meta, ensure_ascii=False)),
        )
        chunk_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO chunks_fts(text, chunk_id, doc_id, path, doc_type, rel_folder) VALUES(?, ?, ?, ?, ?, ?)",
            (ch.text, chunk_id, doc.doc_id, doc.path, doc.doc_type, doc.rel_folder),
        )


def _escape_fts5_query(q: str) -> str:
    """Échappe une requête pour FTS5.
    
    FTS5 a une syntaxe spéciale. Pour éviter les erreurs :
    - Remplacer les apostrophes par des espaces
    - Échapper les guillemets doubles
    - Mettre la requête entre guillemets doubles pour forcer une recherche de phrase
    """
    # Remplacer les apostrophes simples et typographiques par des espaces
    q_clean = q.replace("'", " ").replace("'", " ").replace("'", " ").replace("'", " ")
    # Nettoyer les espaces multiples
    q_clean = " ".join(q_clean.split())
    if not q_clean:
        return '""'
    # Échapper les guillemets doubles en les doublant
    q_escaped = q_clean.replace('"', '""')
    # Mettre entre guillemets doubles pour forcer une recherche de phrase
    # Cela évite que FTS5 interprète les mots comme des opérateurs ou colonnes
    return f'"{q_escaped}"'


def search_fts(
    conn: sqlite3.Connection,
    q: str,
    top_k: int = 10,
    doc_type: Optional[str] = None,
    scope: Optional[str] = None,
) -> List[Dict]:
    # Échapper la requête pour FTS5
    q_escaped = _escape_fts5_query(q)
    # Construire la requête SQL avec la syntaxe FTS5 correcte
    # Utiliser des paramètres liés pour éviter les injections SQL
    query_sql = """
        SELECT
          chunk_id,
          path,
          doc_type,
          rel_folder,
          bm25(chunks_fts) AS rank,
          snippet(chunks_fts, 0, '<<<', '>>>', ' … ', 24) AS snip
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
          AND (? IS NULL OR doc_type = ?)
          AND (? IS NULL OR rel_folder LIKE ? || '%')
        ORDER BY rank
        LIMIT ?;
    """
    rows = conn.execute(
        query_sql,
        (q_escaped, doc_type, doc_type, scope, scope, top_k),
    ).fetchall()

    hits: List[Dict] = []
    for r in rows:
        rank = float(r["rank"]) if r["rank"] is not None else 9999.0
        score = 1.0 / (1.0 + max(0.0, rank))
        hits.append(
            {
                "chunk_id": int(r["chunk_id"]),
                "path": r["path"],
                "doc_type": r["doc_type"],
                "rel_folder": r["rel_folder"],
                "rank": rank,
                "score": score,
                "snippet": r["snip"],
            }
        )
    return hits


def get_chunk(conn: sqlite3.Connection, chunk_id: int) -> Dict:
    row = conn.execute(
        """
        SELECT c.id as chunk_id, c.doc_id, c.chunk_index, c.start_line, c.end_line, c.kind, c.text,
               d.path, d.doc_type, d.rel_folder
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        WHERE c.id = ?;
        """,
        (chunk_id,),
    ).fetchone()
    if not row:
        raise KeyError(f"chunk_id not found: {chunk_id}")
    return dict(row)
