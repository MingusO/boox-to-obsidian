"""Kald til Anthropic Messages API uden eksterne afhaengigheder."""
import base64
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Dict, List

from .prompts import LANGUAGES, RECORD_TOOL, summary_prompt, transcribe_instruction

log = logging.getLogger("claude")

API_URL = "https://api.anthropic.com/v1/messages"
RETRY_CODES = (408, 409, 429, 500, 502, 503, 504, 529)

class ClaudeError(Exception):
    pass


class Claude:
    def __init__(self, api_key: str, model: str, summary_model: str, language: str = "da"):
        self.api_key = api_key
        self.model = model
        self.summary_model = summary_model
        self.language = LANGUAGES.get(language, language)

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        last = "ukendt fejl"
        for attempt in range(5):
            req = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                if e.code in RETRY_CODES:
                    last = f"HTTP {e.code}"
                    time.sleep(min(60, 3 * 2 ** attempt))
                    continue
                raise ClaudeError(f"HTTP {e.code}: {detail}")
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e)
                time.sleep(min(60, 3 * 2 ** attempt))
        raise ClaudeError(f"Opgav efter flere forsoeg: {last}")

    def transcribe(self, pdf_bytes: bytes, notebook: str, hint: str, today: str) -> Dict:
        instruction = transcribe_instruction(notebook, hint, today)
        payload = {
            "model": self.model,
            "max_tokens": 8000,
            "tools": [RECORD_TOOL],
            "tool_choice": {"type": "tool", "name": "record_page"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.b64encode(pdf_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": instruction},
                    ],
                }
            ],
        }
        resp = self._post(payload)
        for block in resp.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "record_page":
                data = block["input"]
                data.setdefault("uncertain_words", [])
                data.setdefault("tasks", [])
                return data
        raise ClaudeError("Svaret indeholdt ikke noget record_page resultat")

    def summarize(self, notebook: str, date: str, pages: List[dict], hint: str) -> str:
        prompt = summary_prompt(notebook, date, pages, hint, self.language)
        payload = {
            "model": self.summary_model,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = self._post(payload)
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        if not text.strip():
            raise ClaudeError("Tom opsummering")
        return text.strip()
