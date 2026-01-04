from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from store.sqlite import connect_db, init_db, search_fts, get_chunk
from llm import ollama_generate


@dataclass(frozen=True)
class Citation:
    path: str
    start_line: int
    end_line: int
    doc_type: str


def build_context(
    db_path: str,
    question: str,
    *,
    top_k: int = 8,
    doc_type: Optional[str] = None,
    scope: Optional[str] = None,
    max_context_chars: int = 18_000,
) -> Tuple[str, List[Dict], List[Citation]]:
    """Retourne context string + hits + citations (ordre des chunks)."""
    conn = connect_db(db_path)
    init_db(conn)
    hits = search_fts(conn, q=question, top_k=top_k, doc_type=doc_type, scope=scope)

    pieces: List[str] = []
    citations: List[Citation] = []
    total = 0
    for i, h in enumerate(hits, start=1):
        ch = get_chunk(conn, int(h["chunk_id"]))
        cite = Citation(
            path=ch["path"],
            start_line=int(ch["start_line"]),
            end_line=int(ch["end_line"]),
            doc_type=ch["doc_type"],
        )
        citations.append(cite)
        header = f"[{i}] {cite.path} ({cite.doc_type}) lines {cite.start_line}-{cite.end_line}"
        block = ch["text"]
        piece = header + "\n" + block
        if total + len(piece) > max_context_chars:
            break
        pieces.append(piece)
        total += len(piece)

    context = "\n\n".join(pieces)
    return context, hits, citations


def answer_with_ollama(
    db_path: str,
    question: str,
    *,
    top_k: int = 8,
    doc_type: Optional[str] = None,
    scope: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: int = 120,
) -> Dict:
    context, hits, citations = build_context(db_path, question, top_k=top_k, doc_type=doc_type, scope=scope)

    prompt = (
        "Tu es un assistant de rétro-documentation de patrimoine OpenVMS (C/SQLMOD/DCL).\n"
        "Réponds en français de façon factuelle et concise.\n"
        "Tu dois citer tes sources sous forme [n] correspondant aux extraits fournis.\n"
        "Si l'information n'est pas présente dans les extraits, dis-le clairement.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"EXTRAITS (avec identifiants [n]):\n{context}\n\n"
        "RÉPONSE (avec citations [n]):"
    )

    response = ollama_generate(prompt, model=model, base_url=base_url, timeout_s=timeout_s)

    return {
        "question": question,
        "answer": response,
        "hits": hits,
        "citations": [c.__dict__ for c in citations],
        "context": context,
    }


# -------------------------
# Rules mode (no LLM)
# -------------------------

_DCL_CMD_RE = re.compile(
    r"^\s*\$\s*(RUN|MCR|PIPE|SUBMIT|COPY|APPEND|RENAME|DELETE|PURGE|SET|ON|GOTO|CALL|@)\b(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_DCL_LABEL_RE = re.compile(r"^\s*\$([A-Za-z0-9_]+):\s*$", re.MULTILINE)
_DCL_ONERR_RE = re.compile(r"^\s*\$\s*ON\s+ERROR\b(.*)$", re.IGNORECASE | re.MULTILINE)
_DCL_EXIT_RE = re.compile(r"^\s*\$\s*(EXIT|STOP|LOGOUT)\b(.*)$", re.IGNORECASE | re.MULTILINE)

_C_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_SQL_TABLE_RE = re.compile(r"\bFROM\s+([A-Za-z0-9_\.]+)|\bJOIN\s+([A-Za-z0-9_\.]+)|\bUPDATE\s+([A-Za-z0-9_\.]+)|\bINTO\s+([A-Za-z0-9_\.]+)", re.IGNORECASE)


def _extract_dcl_features(text: str) -> Dict:
    labels = [m.group(1) for m in _DCL_LABEL_RE.finditer(text)]
    onerr = [m.group(1).strip() for m in _DCL_ONERR_RE.finditer(text)]
    exits = [m.group(1).upper() for m in _DCL_EXIT_RE.finditer(text)]
    cmds = []
    for m in _DCL_CMD_RE.finditer(text):
        cmd = m.group(1).upper()
        rest = (m.group(2) or "").strip()
        # keep compact preview
        cmds.append({"cmd": cmd, "arg": rest[:160]})
    return {"labels": labels[:50], "on_error": onerr[:20], "exits": exits[:20], "commands": cmds[:80]}


def _extract_c_features(text: str) -> Dict:
    # Very light: most frequent call names (excluding obvious keywords)
    names = [m.group(1) for m in _C_CALL_RE.finditer(text)]
    stop = {"if", "for", "while", "switch", "return", "sizeof", "typedef"}
    filt = [n for n in names if n not in stop and len(n) <= 40]
    # count top
    counts: Dict[str, int] = {}
    for n in filt:
        counts[n] = counts.get(n, 0) + 1
    top = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:20]
    return {"top_calls": top}


def _extract_sql_features(text: str) -> Dict:
    tables = []
    for m in _SQL_TABLE_RE.finditer(text):
        for g in m.groups():
            if g:
                tables.append(g)
    # normalize
    norm = []
    for t in tables:
        t = t.strip().rstrip(";")
        if t:
            norm.append(t)
    uniq = []
    seen = set()
    for t in norm:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            uniq.append(t)
    return {"tables": uniq[:40]}


def answer_rules(
    db_path: str,
    question: str,
    *,
    top_k: int = 8,
    doc_type: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict:
    """Produit une explication structurée à partir des extraits, sans appel LLM."""
    context, hits, citations = build_context(db_path, question, top_k=top_k, doc_type=doc_type, scope=scope)

    # Build per-citation features (using chunk text, not the header)
    conn = connect_db(db_path)
    init_db(conn)

    per_source = []
    for i, h in enumerate(hits, start=1):
        ch = get_chunk(conn, int(h["chunk_id"]))
        dtype = ch["doc_type"]
        txt = ch["text"]
        features = {}
        if dtype == "dcl":
            features = _extract_dcl_features(txt)
        elif dtype == "c":
            features = _extract_c_features(txt)
        elif dtype == "sqlmod":
            features = _extract_sql_features(txt)
        per_source.append({
            "n": i,
            "path": ch["path"],
            "doc_type": dtype,
            "start_line": int(ch["start_line"]),
            "end_line": int(ch["end_line"]),
            "features": features,
        })

    # Simple narrative template (no hallucinations): only refer to extracted items.
    lines = []
    lines.append("Synthèse basée uniquement sur les extraits fournis :")
    for src in per_source:
        n = src["n"]
        dtype = src["doc_type"]
        lines.append(f"")
        lines.append(f"[{n}] {src['path']} ({dtype}) lignes {src['start_line']}-{src['end_line']} :")
        feat = src["features"] or {}
        if dtype == "dcl":
            cmds = feat.get("commands", [])
            if cmds:
                lines.append(f"- Commandes DCL repérées : " + ", ".join(sorted({c['cmd'] for c in cmds})) )
                # show a few
                preview = cmds[:8]
                for c in preview:
                    arg = f" {c['arg']}" if c.get("arg") else ""
                    lines.append(f"  - {c['cmd']}{arg}")
            if feat.get("on_error"):
                for oe in feat["on_error"][:3]:
                    lines.append(f"- Gestion d'erreur (ON ERROR) : {oe}")
            if feat.get("exits"):
                lines.append(f"- Sorties (EXIT/STOP/LOGOUT) repérées : " + ", ".join(sorted(set(feat["exits"])) ))
            if feat.get("labels"):
                lines.append(f"- Labels repérés : " + ", ".join(feat["labels"][:8]) + (" ..." if len(feat["labels"]) > 8 else ""))
        elif dtype == "c":
            calls = feat.get("top_calls", [])
            if calls:
                lines.append("- Appels de fonctions les plus fréquents (indicatif) :")
                for name, cnt in calls[:10]:
                    lines.append(f"  - {name} (x{cnt})")
        elif dtype == "sqlmod":
            tables = feat.get("tables", [])
            if tables:
                lines.append("- Tables/objets SQL repérés : " + ", ".join(tables[:12]) + (" ..." if len(tables) > 12 else ""))
        else:
            # generic: just indicate that content is present
            lines.append("- Contenu texte disponible (aucune extraction spécifique appliquée).")

    answer_text = "\n".join(lines)

    return {
        "question": question,
        "answer": answer_text,
        "mode": "rules",
        "hits": hits,
        "citations": [c.__dict__ for c in citations],
        "context": context,
        "per_source": per_source,
    }
