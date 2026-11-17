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
        "anthropic_api_key": "k", "drive_token": "{\"access_token\":\"a\"}",
        "notebooks": [{"name": "Kompan", "drive_path": "/onyx/Kompan.pdf"}],
    }))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = config.load(str(opts))
    assert cfg.notebooks[0].drive_path == "onyx/Kompan.pdf"
    assert config.validate(cfg) == []
    cfg.drive_token = "ikke json"
    assert any("drive_token" in p for p in config.validate(cfg))
