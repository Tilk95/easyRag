from __future__ import annotations

import json
import os
import socket
import urllib.request
from typing import Optional


class LlmError(RuntimeError):
    pass


def ollama_generate(
    prompt: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: int = 120,
) -> str:
    """Appel minimal à Ollama /api/generate (stream=false), via urllib (stdlib only)."""
    model = model or os.getenv("RAGLITE_OLLAMA_MODEL", "llama3.1")
    base_url = base_url or os.getenv("RAGLITE_OLLAMA_URL", "http://localhost:11434")
    url = base_url.rstrip("/") + "/api/generate"

    payload = {"model": model, "prompt": prompt, "stream": False}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            error_msg = f"Modèle Ollama '{model}' non trouvé (404).\n"
            error_msg += f"Vérifiez que le modèle existe avec: ollama list\n"
            error_msg += f"Ou téléchargez-le avec: ollama pull {model}\n"
            error_msg += f"Astuce: Utilisez --mode context pour éviter l'appel LLM"
        else:
            error_msg = f"Erreur HTTP {e.code} depuis Ollama: {e}"
        raise LlmError(error_msg) from e
    except (urllib.error.URLError, socket.timeout) as e:
        error_msg = f"Ollama unreachable or timed out: {e}"
        if isinstance(e, urllib.error.URLError) and "Connection refused" in str(e):
            error_msg += "\n\nAstuce: Utilisez --mode context pour éviter l'appel LLM, ou démarrez Ollama avec: ollama serve"
        raise LlmError(error_msg) from e

    try:
        obj = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise LlmError(f"Invalid JSON from Ollama: {e}") from e

    if "error" in obj and obj["error"]:
        raise LlmError(str(obj["error"]))

    return obj.get("response", "").strip()
