"""Kald til Google Gemini API (gratis niveau findes) uden eksterne afhaengigheder."""
import base64
import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List

from .claude import RETRY_CODES, ClaudeError
from .prompts import LANGUAGES, RECORD_TOOL, summary_prompt, transcribe_instruction

log = logging.getLogger("gemini")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MIN_INTERVAL_SECONDS = 5.0


def _text_of(resp: dict) -> str:
    candidates = resp.get("candidates") or []
    if not candidates:
        feedback = resp.get("promptFeedback") or {}
        raise ClaudeError(f"Gemini gav intet svar ({feedback.get('blockReason', 'ukendt aarsag')})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ClaudeError("Gemini svarede ikke med gyldig JSON")


class Gemini:
    def __init__(self, api_key: str, model: str, language: str = "da"):
        self.api_key = api_key
        self.model = model
        self.language = LANGUAGES.get(language, language)
        self._last_call = 0.0

    def _post(self, payload: dict) -> dict:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        body = json.dumps(payload).encode("utf-8")
        headers = {"content-type": "application/json", "x-goog-api-key": self.api_key}
        url = f"{BASE_URL}/{self.model}:generateContent"
        last = "ukendt fejl"
        for attempt in range(5):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    self._last_call = time.monotonic()
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                if e.code in RETRY_CODES:
                    last = f"HTTP {e.code}"
                    time.sleep(min(90, 8 * 2 ** attempt))
                    continue
                raise ClaudeError(f"HTTP {e.code}: {detail}")
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e)
                time.sleep(min(60, 3 * 2 ** attempt))
        raise ClaudeError(f"Opgav efter flere forsoeg: {last}")

    def transcribe(self, pdf_bytes: bytes, notebook: str, hint: str, today: str) -> Dict:
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf_bytes).decode("ascii")}},
                        {"text": transcribe_instruction(notebook, hint, today, as_tool=False)},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": RECORD_TOOL["input_schema"],
            },
        }
        data = _parse_json(_text_of(self._post(payload)))
        data.setdefault("uncertain_words", [])
        data.setdefault("tasks", [])
        for key in ("is_blank", "date", "title", "raw_text", "corrected_text"):
            data.setdefault(key, False if key == "is_blank" else "")
        return data

    def summarize(self, notebook: str, date: str, pages: List[dict], hint: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": summary_prompt(notebook, date, pages, hint, self.language)}]}],
        }
        text = _text_of(self._post(payload)).strip()
        if not text:
            raise ClaudeError("Tom opsummering")
        return text
