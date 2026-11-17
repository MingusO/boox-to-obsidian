import json
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Notebook:
    name: str
    drive_path: str
    category: str = "Kursus"
    hint: str = ""
    provider: str = ""
    folder: str = ""


@dataclass
class Config:
    provider: str = "gemini"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    model: str = "claude-sonnet-5-5"
    summary_model: str = "claude-sonnet-5-5"
    language: str = "da"
    drive_token: str = ""
    poll_minutes: int = 15
    settle_minutes: int = 30
    max_pages_per_run: int = 25
    import_existing: bool = False
    timezone: str = "Europe/Copenhagen"
    vault_path: str = "/share/obsidian_vault"
    notes_folder: str = "Noter"
    attachments_folder: str = "Noter/Bilag"
    daily_folder: str = "Daily"
    daily_format: str = "YYYY-MM-DD"
    daily_template: str = ""
    summary_hour: int = 21
    notify_service: str = ""
    obsidian_sync: bool = False
    obsidian_email: str = ""
    obsidian_password: str = ""
    obsidian_mfa: str = ""
    obsidian_vault_name: str = ""
    obsidian_e2ee_password: str = ""
    notebooks: List[Notebook] = field(default_factory=list)
    data_dir: str = "/data"


def load(path: str = "") -> Config:
    path = path or os.environ.get("OPTIONS_PATH", "/data/options.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    cfg = Config(data_dir=os.environ.get("DATA_DIR", "/data"))
    for key, value in raw.items():
        if key == "notebooks":
            continue
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    cfg.notebooks = [
        Notebook(
            name=n["name"].strip(),
            drive_path=n["drive_path"].strip().strip("/"),
            category=(n.get("category") or "Kursus").strip(),
            hint=(n.get("hint") or "").strip(),
            provider=(n.get("provider") or "").strip(),
            folder=(n.get("folder") or "").strip().strip("/"),
        )
        for n in raw.get("notebooks", [])
    ]
    return cfg


def validate(cfg: Config) -> List[str]:
    problems = []
    used = {n.provider or cfg.provider for n in cfg.notebooks}
    unknown = used - {"claude_api", "gemini"}
    if unknown:
        problems.append("Ukendt provider: " + ", ".join(sorted(unknown)))
    if "claude_api" in used and not cfg.anthropic_api_key:
        problems.append("anthropic_api_key mangler (bruges af mindst en notesbog)")
    if "gemini" in used and not cfg.gemini_api_key:
        problems.append("gemini_api_key mangler (bruges af mindst en notesbog)")
    if not cfg.notebooks:
        problems.append("Der er ingen notesboeger i indstillingerne")
    if not cfg.drive_token:
        problems.append("drive_token mangler")
    else:
        try:
            json.loads(cfg.drive_token)
        except ValueError:
            problems.append("drive_token er ikke gyldig JSON. Kopier hele blokken fra rclone authorize")
    names = [n.name for n in cfg.notebooks]
    if len(set(names)) != len(names):
        problems.append("Notesboegerne skal have unikke navne")
    return problems
