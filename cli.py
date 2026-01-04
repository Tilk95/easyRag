from __future__ import annotations

import argparse
import json
from typing import List, Optional

from indexing import index_root
from store.sqlite import connect_db, init_db, search_fts, get_chunk
from api_server import serve as serve_http
from rag import build_context, answer_with_ollama, answer_rules


def cmd_index(args: argparse.Namespace) -> None:
    include = args.include_exts.split(",") if args.include_exts else None
    index_root(args.db, args.root, include_exts=include, verbose=not args.quiet)


def cmd_query(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)
    init_db(conn)
    hits = search_fts(conn, q=args.q, top_k=args.top_k, doc_type=args.type, scope=args.scope)

    if args.format == "json":
        out_hits = []
        for h in hits:
            ch = get_chunk(conn, int(h["chunk_id"]))
            out_hits.append({**h, "start_line": ch["start_line"], "end_line": ch["end_line"], "kind": ch["kind"]})
        print(json.dumps({"query": args.q, "top_k": args.top_k, "hits": out_hits}, ensure_ascii=False, indent=2))
        return

    print(f"Query: {args.q}")
    for i, h in enumerate(hits, start=1):
        ch = get_chunk(conn, int(h["chunk_id"]))
        print(f"\n#{i} score={h['score']:.4f} rank={h['rank']:.4f}")
        print(f"  {h['path']}  ({h['doc_type']})  folder='{h['rel_folder']}'  lines {ch['start_line']}-{ch['end_line']}  kind={ch['kind']}")
        print(f"  {h['snippet']}")


def cmd_serve(args: argparse.Namespace) -> None:
    serve_http(args.db, host=args.host, port=args.port)


def cmd_explain(args: argparse.Namespace) -> None:
    # mode=context -> no llm call, just show retrieved evidence
    if args.mode == "context":
        context, hits, citations = build_context(args.db, args.question, top_k=args.top_k, doc_type=args.type, scope=args.scope)
        payload = {
            "question": args.question,
            "hits": hits,
            "citations": [c.__dict__ for c in citations],
            "context": context,
        }
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Question: {args.question}\n")
            print(context)
        return
    if args.mode == "rules":
        result = answer_rules(args.db, args.question, top_k=args.top_k, doc_type=args.type, scope=args.scope)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["answer"])
            print("\nCitations:")
            for i, c in enumerate(result["citations"], start=1):
                print(f"  [{i}] {c['path']} lines {c['start_line']}-{c['end_line']} ({c['doc_type']})")
        return

    result = answer_with_ollama(
        args.db,
        args.question,
        top_k=args.top_k,
        doc_type=args.type,
        scope=args.scope,
        model=args.model,
        base_url=args.base_url,
        timeout_s=args.timeout_s,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["answer"])
        print("\nCitations:")
        for i, c in enumerate(result["citations"], start=1):
            print(f"  [{i}] {c['path']} lines {c['start_line']}-{c['end_line']} ({c['doc_type']})")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="raglite",
        description="RAG minimaliste (SQLite FTS + chunkers) — stdlib only"
    )
    # Ajouter alias --h pour --help
    p.add_argument('--h', action='help', help='Afficher ce message d\'aide et quitter (alias de --help)')
    sub = p.add_subparsers(dest="cmd", required=False)  # Pas required pour permettre --h sans commande

    p_index = sub.add_parser("index", help="Indexer un répertoire dans SQLite+FTS")
    p_index.add_argument("--root", required=True)
    p_index.add_argument("--db", required=True)
    p_index.add_argument("--include-exts", default="")
    p_index.add_argument("--quiet", action="store_true")
    p_index.set_defaults(func=cmd_index)

    p_query = sub.add_parser("query", help="Interroger l'index (FTS)")
    p_query.add_argument("--db", required=True)
    p_query.add_argument("--q", required=True)
    p_query.add_argument("--top-k", type=int, default=10)
    p_query.add_argument("--type", default=None)
    p_query.add_argument("--scope", default=None)
    p_query.add_argument("--format", default="text", choices=("text", "json"))
    p_query.set_defaults(func=cmd_query)

    p_explain = sub.add_parser("explain", help="RAG 'answer' : récupère des extraits puis (optionnel) appelle un LLM")
    p_explain.add_argument("--db", required=True)
    p_explain.add_argument("--question", required=True)
    p_explain.add_argument("--top-k", type=int, default=8)
    p_explain.add_argument("--type", default=None)
    p_explain.add_argument("--scope", default=None)
    p_explain.add_argument("--mode", default="ollama", choices=("ollama", "context", "rules"), help="context: pas d'appel LLM")
    p_explain.add_argument("--model", default=None, help="Ollama model (sinon env RAGLITE_OLLAMA_MODEL ou llama3.1)")
    p_explain.add_argument("--base-url", default=None, help="Ollama base url (sinon env RAGLITE_OLLAMA_URL ou http://localhost:11434)")
    p_explain.add_argument("--timeout-s", type=int, default=120)
    p_explain.add_argument("--format", default="text", choices=("text", "json"))
    p_explain.set_defaults(func=cmd_explain)

    p_serve = sub.add_parser("serve", help="Lancer un serveur HTTP JSON (pour UI legacy)")
    p_serve.add_argument("--db", required=True)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8787)
    p_serve.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    
    # Si aucun argument n'est fourni, afficher l'aide
    if argv is None:
        argv = []
    if len(argv) == 0:
        parser.print_help()
        return 0
    
    # Vérifier si --h ou --help est passé
    if '--h' in argv or '--help' in argv or '-h' in argv:
        parser.print_help()
        return 0
    
    args = parser.parse_args(argv)
    
    # Si aucune commande n'est fournie, afficher l'aide
    if not hasattr(args, 'func') or args.cmd is None:
        parser.print_help()
        return 0
    
    args.func(args)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
