from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict
from urllib.parse import parse_qs, urlparse

from store.sqlite import connect_db, init_db, search_fts, get_chunk
from rag import answer_with_ollama, build_context, answer_rules


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "raglite/0.2"

    def _send_json(self, status: int, payload: Dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/health":
            return self._send_json(200, {"ok": True})

        if parsed.path == "/search":
            q = (qs.get("q") or [""])[0].strip()
            if not q:
                return self._send_json(400, {"error": "missing q"})
            top_k = int((qs.get("top_k") or ["10"])[0])
            doc_type = (qs.get("type") or [None])[0]
            scope = (qs.get("scope") or [None])[0]

            conn = connect_db(self.server.db_path)  # type: ignore[attr-defined]
            hits = search_fts(conn, q=q, top_k=top_k, doc_type=doc_type, scope=scope)
            out_hits = []
            for h in hits:
                ch = get_chunk(conn, int(h["chunk_id"]))
                out_hits.append({**h, "start_line": ch["start_line"], "end_line": ch["end_line"], "kind": ch["kind"]})
            return self._send_json(200, {"query": q, "top_k": top_k, "hits": out_hits})

        if parsed.path == "/chunk":
            cid = (qs.get("id") or [""])[0].strip()
            if not cid.isdigit():
                return self._send_json(400, {"error": "missing or invalid id"})
            conn = connect_db(self.server.db_path)  # type: ignore[attr-defined]
            try:
                ch = get_chunk(conn, int(cid))
            except KeyError:
                return self._send_json(404, {"error": "chunk not found"})
            return self._send_json(200, ch)

        return self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/answer":
            return self._send_json(404, {"error": "not found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return self._send_json(400, {"error": "invalid json"})

        question = (payload.get("question") or "").strip()
        if not question:
            return self._send_json(400, {"error": "missing question"})

        top_k = int(payload.get("top_k") or 8)
        doc_type = payload.get("type")
        scope = payload.get("scope")
        mode = (payload.get("mode") or "ollama").lower()
        model = payload.get("model")
        base_url = payload.get("base_url")
        timeout_s = int(payload.get("timeout_s") or 120)

        db_path = self.server.db_path  # type: ignore[attr-defined]

        if mode == "context":
            context, hits, citations = build_context(db_path, question, top_k=top_k, doc_type=doc_type, scope=scope)
            return self._send_json(200, {"question": question, "context": context, "hits": hits, "citations": [c.__dict__ for c in citations]})

        if mode == "rules":
            try:
                result = answer_rules(db_path, question, top_k=top_k, doc_type=doc_type, scope=scope)
                return self._send_json(200, result)
            except Exception as e:
                return self._send_json(502, {"error": str(e)})

        try:
            result = answer_with_ollama(
                db_path,
                question,
                top_k=top_k,
                doc_type=doc_type,
                scope=scope,
                model=model,
                base_url=base_url,
                timeout_s=timeout_s,
            )
            return self._send_json(200, result)
        except Exception as e:
            return self._send_json(502, {"error": str(e)})

    def log_message(self, fmt, *args):
        return


def serve(db_path: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    conn = connect_db(db_path)
    init_db(conn)
    conn.close()

    httpd = ThreadingHTTPServer((host, port), ApiHandler)
    httpd.db_path = db_path  # type: ignore[attr-defined]
    print(f"[serve] http://{host}:{port}  db={db_path}")
    httpd.serve_forever()
