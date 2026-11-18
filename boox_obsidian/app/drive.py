"""Henter notesbogens PDF fra Google Drive med rclone (kun laesning)."""
import logging
import os
import subprocess
from typing import Optional

from .config import Config, Notebook
from .util import safe_name

log = logging.getLogger("drive")


class Drive:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.inbox = os.path.join(cfg.data_dir, "inbox")
        self.conf = os.path.join(cfg.data_dir, "rclone.conf")
        os.makedirs(self.inbox, exist_ok=True)
        self._write_conf()

    def _write_conf(self) -> None:
        text = "[gdrive]\ntype = drive\nscope = drive.readonly\n"
        if self.cfg.drive_client_id:
            text += f"client_id = {self.cfg.drive_client_id}\nclient_secret = {self.cfg.drive_client_secret}\n"
        text += f"token = {self.cfg.drive_token}\n"
        fd = os.open(self.conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text)

    def fetch(self, nb: Notebook) -> Optional[str]:
        dest = os.path.join(self.inbox, safe_name(nb.name) + ".pdf")
        cmd = [
            "rclone", "copyto", f"gdrive:{nb.drive_path}", dest,
            "--config", self.conf, "--retries", "2", "--low-level-retries", "3",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log.error("rclone fejlede for %s: %s", nb.name, e)
            return dest if os.path.exists(dest) else None
        if res.returncode != 0:
            err = res.stderr or ""
            if "rateLimitExceeded" in err or "RATE_LIMIT_EXCEEDED" in err:
                log.error(
                    "Google Drive afviste kaldet for %s fordi kvoten er brugt op. Det sker, naar man bruger rclones "
                    "faelles klient. Opret dit eget Google client id og udfyld drive_client_id og drive_client_secret "
                    "(se guiden, trin 3).", nb.name)
            else:
                log.error("rclone fejl for %s: %s", nb.name, err.strip()[-400:])
            return dest if os.path.exists(dest) else None
        return dest if os.path.exists(dest) else None
