import logging
import os
import signal
import sys
import threading

from . import __version__, config
from .claude import Claude
from .drive import Drive
from .gemini import Gemini
from .notify import Notifier
from .obsidian_sync import NullSync, ObsidianSync
from .pipeline import Pipeline
from .state import State


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("boox")
    cfg = config.load()
    log.info("Boox til Obsidian %s starter med %d notesbog(er)", __version__, len(cfg.notebooks))

    problems = config.validate(cfg)
    if problems:
        for p in problems:
            log.error("Indstilling: %s", p)
        log.error("Ret indstillingerne i add on'et og start det igen.")
        return 1

    os.makedirs(cfg.vault_path, exist_ok=True)
    state = State(os.path.join(cfg.data_dir, "state.db"))
    used = {n.provider or cfg.provider for n in cfg.notebooks}
    providers = {}
    if "claude_api" in used:
        providers["claude_api"] = Claude(cfg.anthropic_api_key, cfg.model, cfg.summary_model, cfg.language)
    if "gemini" in used:
        providers["gemini"] = Gemini(cfg.gemini_api_key, cfg.gemini_model, cfg.language)
    drive = Drive(cfg)
    obsidian = ObsidianSync(cfg) if cfg.obsidian_sync else NullSync()
    obsidian.ensure_setup()
    pipeline = Pipeline(cfg, state, providers, drive.fetch, Notifier(cfg.notify_service), obsidian)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    while not stop.is_set():
        try:
            pipeline.run_cycle()
        except Exception:
            log.exception("Uventet fejl i koerslen")
        stop.wait(cfg.poll_minutes * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
