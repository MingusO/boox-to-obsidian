"""Kald til Anthropic Messages API uden eksterne afhaengigheder."""
import base64
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Dict, List

log = logging.getLogger("claude")

API_URL = "https://api.anthropic.com/v1/messages"
RETRY_CODES = (408, 409, 429, 500, 502, 503, 504, 529)
LANGUAGES = {"da": "dansk", "en": "engelsk"}

RECORD_TOOL = {
    "name": "record_page",
    "description": "Gem resultatet af laesningen af en side med haandskrevne noter.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_blank": {"type": "boolean", "description": "Sand hvis siden ingen skrift har."},
            "date": {
                "type": "string",
                "description": "Datoen der staar skrevet paa siden som YYYY-MM-DD. Tom streng hvis ingen dato er skrevet.",
            },
            "title": {"type": "string", "description": "Kort titel paa siden, hoejst otte ord. Tom streng hvis tvivl."},
            "raw_text": {"type": "string", "description": "Noejagtig transskription af skriften, ogsaa med fejl."},
            "corrected_text": {
                "type": "string",
                "description": "Samme indhold som raw_text med stavefejl og tydelige slipfejl rettet, formateret som markdown.",
            },
            "uncertain_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ord eller steder du er usikker paa at have laest rigtigt.",
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Udtrykkelige opgaver, aftaler og deadlines der staar paa siden.",
            },
        },
        "required": ["is_blank", "date", "title", "raw_text", "corrected_text", "uncertain_words", "tasks"],
    },
}


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
        instruction = (
            f"Dette er en side fra min haandskrevne notesbog '{notebook}'. "
            f"Dagens dato er {today}. "
            "Laes al haandskrift paa siden og kald record_page. "
            "Regler: Bevar sproget i hver passage, oversaet aldrig. "
            "raw_text er en tro transskription. corrected_text er det samme indhold med stavefejl rettet "
            "og pænt struktureret som markdown (overskrifter, punktlister, tabeller hvis det er skrevet som tabel, "
            "formler som LaTeX mellem dollartegn). Tilfoej aldrig indhold der ikke staar paa siden. "
            "Skriv [?] hvor et ord er ulaeseligt, og list usikre ord i uncertain_words. "
            "Hvis siden viser en dato, returner den som YYYY-MM-DD, ellers en tom streng."
        )
        if hint:
            instruction += f" Baggrund for notesbogen: {hint}"
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
        joined = "\n\n".join(
            f"[Side {p['idx'] + 1}{': ' + p['title'] if p['title'] else ''}]\n{p['text']}" for p in pages
        )
        instruction = (
            f"Her er mine noter fra notesbogen '{notebook}' den {date}. "
            f"Skriv en kort log paa {self.language} som jeg hurtigt kan skimme senere. "
            "Format: foerst to til fem saetninger om hvad der skete og blev gennemgaaet. "
            "Derefter, hvis relevant, en liste med overskriften 'Nøglepunkter' og en liste med overskriften "
            "'Opgaver og aftaler'. Brug stjerne som punkttegn. Opfind intet, og brug ikke overskrifter foroven. "
            "Svar kun med selve teksten."
        )
        if hint:
            instruction += f" Baggrund: {hint}"
        payload = {
            "model": self.summary_model,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": f"{instruction}\n\nNoter:\n{joined}"}],
        }
        resp = self._post(payload)
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        if not text.strip():
            raise ClaudeError("Tom opsummering")
        return text.strip()
