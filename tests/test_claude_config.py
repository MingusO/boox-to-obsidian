import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "boox_obsidian"))

from app import config  # noqa: E402
from app.claude import Claude  # noqa: E402


def test_transcribe_builds_pdf_request_and_reads_tool_result():
    c = Claude("nøgle", "model-x", "model-y")
    seen = {}

    def fake_post(payload):
        seen.update(payload)
        return {"content": [{"type": "tool_use", "name": "record_page", "input": {
            "is_blank": False, "date": "", "title": "t", "raw_text": "r", "corrected_text": "c"}}]}

    c._post = fake_post
    out = c.transcribe(b"%PDF-1.7 test", "Kompan", "", "2026-11-17")
    assert out["corrected_text"] == "c" and out["tasks"] == [] and out["uncertain_words"] == []
    doc = seen["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["media_type"] == "application/pdf"
    assert seen["tool_choice"]["name"] == "record_page"
    assert seen["model"] == "model-x"


def test_summarize_uses_summary_model():
    c = Claude("k", "m1", "m2")
    c._post = lambda p: {"content": [{"type": "text", "text": " Hej "}], "model_used": p["model"]}
    assert c.summarize("Kompan", "2026-11-17", [{"idx": 0, "title": "", "text": "x"}], "") == "Hej"


def test_config_load_and_validate(tmp_path, monkeypatch):
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({
        "provider": "claude_api", "anthropic_api_key": "k", "drive_token": "{\"access_token\":\"a\"}",
        "notebooks": [{"name": "Kompan", "drive_path": "/onyx/Kompan.pdf"}],
    }))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = config.load(str(opts))
    assert cfg.notebooks[0].drive_path == "onyx/Kompan.pdf"
    assert config.validate(cfg) == []
    cfg.drive_token = "ikke json"
    assert any("drive_token" in p for p in config.validate(cfg))


def test_gemini_request_and_parsing():
    from app.gemini import Gemini

    g = Gemini("nøgle", "gemini-flash-latest")
    seen = {}

    def fake_post(payload):
        seen.update(payload)
        body = '```json\n{"is_blank": false, "date": "2026-11-17", "title": "t", "raw_text": "r", "corrected_text": "c"}\n```'
        return {"candidates": [{"content": {"parts": [{"thought": True, "text": "tanker"}, {"text": body}]}}]}

    g._post = fake_post
    out = g.transcribe(b"%PDF-1.7 test", "Kompan", "", "2026-11-17")
    assert out["corrected_text"] == "c" and out["tasks"] == [] and out["date"] == "2026-11-17"
    part = seen["contents"][0]["parts"][0]["inline_data"]
    assert part["mime_type"] == "application/pdf"
    assert seen["generationConfig"]["responseMimeType"] == "application/json"
    assert "properties" in seen["generationConfig"]["responseJsonSchema"]


def test_provider_validation_and_routing(tmp_path):
    cfg = config.Config(
        provider="gemini", gemini_api_key="g", drive_token="{}",
        notebooks=[config.Notebook("A", "a.pdf"), config.Notebook("B", "b.pdf", provider="claude_api")],
    )
    assert any("anthropic_api_key" in p for p in config.validate(cfg))
    cfg.anthropic_api_key = "k"
    assert config.validate(cfg) == []
    cfg.notebooks[0].provider = "ukendt"
    assert any("Ukendt provider" in p for p in config.validate(cfg))
