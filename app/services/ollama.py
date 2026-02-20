from __future__ import annotations

import json
import os
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


def chat_json(system_prompt: str, user_prompt: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
    }

    response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    content = data.get("message", {}).get("content", "{}")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Model did not return valid JSON") from exc
