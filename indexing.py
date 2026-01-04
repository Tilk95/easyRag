from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List, Optional

from models import Document
from chunkers.registry import default_registry
from store.sqlite import connect_db, init_db, upsert_document, replace_chunks, should_reindex


def sha256_text(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8", errors="replace"))
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.hexdigest()


def safe_read_text(path: Path, max_bytes: int = 20_000_000) -> str:
    st = path.stat()
    if st.st_size > max_bytes:
        raise ValueError(f"File too large for MVP ({st.st_size} bytes): {path}")
    data = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin1", errors="replace")


def normalize_rel_folder(root: Path, p: Path) -> str:
    try:
        rel = p.parent.relative_to(root)
        s = str(rel).replace("\\", "/")
        return s if s != "." else ""
    except Exception:
        return ""


def detect_doc_type(p: Path, text_preview: str = "") -> str:
    ext = p.suffix.lower()
    if ext in (".com", ".dcl"):
        return "dcl"
    if ext in (".c", ".h", ".hpp", ".hh", ".cc", ".cpp"):
        return "c"
    if ext in (".sql", ".sqlmod", ".sc", ".ddl"):
        return "sqlmod"
    if text_preview:
        lines = text_preview.splitlines()[:80]
        if lines:
            dollar = sum(1 for ln in lines if ln.lstrip().startswith("$"))
            if dollar >= max(10, int(0.6 * len(lines))):
                return "dcl"
    return "text"


def iter_source_files(root: Path, include_exts: Optional[List[str]] = None) -> Iterable[Path]:
    default_exts = {
        ".com", ".dcl", ".c", ".h", ".sql", ".sqlmod", ".sc", ".ddl",
        ".txt", ".md", ".rst", ".log", ".ini", ".cfg", ".conf",
        ".json", ".yaml", ".yml", ".csv"
    }
    exts = set(e.lower() for e in (include_exts or [])) or default_exts
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def index_root(db_path: str, root: str, include_exts: Optional[List[str]] = None, verbose: bool = True) -> None:
    rootp = Path(root).resolve()
    if not rootp.exists():
        raise FileNotFoundError(root)

    reg = default_registry()
    conn = connect_db(db_path)
    init_db(conn)

    total = updated = ignored = 0

    for p in iter_source_files(rootp, include_exts=include_exts):
        total += 1
        try:
            file_hash = sha256_file(p)
            doc_id = sha256_text(str(p.resolve()))
            if not should_reindex(conn, doc_id, file_hash):
                continue

            text = safe_read_text(p)
            preview = "\n".join(text.splitlines()[:120])
            doc_type = detect_doc_type(p, preview)
            rel_folder = normalize_rel_folder(rootp, p)
            mtime = int(p.stat().st_mtime)

            doc = Document(
                doc_id=doc_id,
                path=str(p),
                rel_folder=rel_folder,
                doc_type=doc_type,
                text=text,
                meta={"source_root": str(rootp), "filename": p.name},
            )

            chunker = reg.resolve(doc.doc_type)
            chunks = chunker.chunk(doc)

            upsert_document(conn, doc, mtime, file_hash)
            replace_chunks(conn, doc, chunks)
            conn.commit()
            updated += 1
            if verbose and updated % 50 == 0:
                print(f"[index] updated={updated} scanned={total}")
        except Exception as e:
            ignored += 1
            if verbose:
                print(f"[index][skip] {p} -> {e}")
    if verbose:
        print(f"[index] done. scanned={total} updated={updated} ignored={ignored} db={db_path}")
