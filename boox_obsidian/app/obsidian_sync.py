"""Valgfri synkronisering med Obsidian Sync via den officielle Obsidian Headless klient (beta)."""
import logging
import os
import shutil
import subprocess

from .config import Config

log = logging.getLogger("obsidian")


class NullSync:
    def ensure_setup(self) -> None:
        pass

    def sync(self) -> None:
        pass


class ObsidianSync:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        home = os.path.join(cfg.data_dir, "home")
        os.makedirs(home, exist_ok=True)
        self.env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=os.path.join(home, ".config"))
        self.ready = False

    def _run(self, args, timeout=900):
        return subprocess.run(
            ["ob", *args], capture_output=True, text=True, timeout=timeout, env=self.env, stdin=subprocess.DEVNULL
        )

    def ensure_setup(self) -> None:
        if shutil.which("ob") is None:
            log.error("Kommandoen 'ob' findes ikke. Obsidian Headless blev ikke installeret i billedet.")
            return
        os.makedirs(self.cfg.vault_path, exist_ok=True)
        try:
            listing = self._run(["sync-list-local"])
            if self.cfg.vault_path in (listing.stdout or ""):
                self.ready = True
                return
            if self.cfg.obsidian_email and self.cfg.obsidian_password:
                login = ["login", "--email", self.cfg.obsidian_email, "--password", self.cfg.obsidian_password]
                if self.cfg.obsidian_mfa:
                    login += ["--mfa", self.cfg.obsidian_mfa]
                res = self._run(login)
                if res.returncode != 0:
                    log.error("Obsidian login fejlede: %s", (res.stderr or res.stdout).strip()[-300:])
                    return
            setup = [
                "sync-setup", "--vault", self.cfg.obsidian_vault_name,
                "--path", self.cfg.vault_path, "--device-name", "Home Assistant",
            ]
            if self.cfg.obsidian_e2ee_password:
                setup += ["--password", self.cfg.obsidian_e2ee_password]
            res = self._run(setup)
            if res.returncode != 0:
                log.error("Obsidian sync setup fejlede: %s", (res.stderr or res.stdout).strip()[-300:])
                return
            log.info("Obsidian Sync er sat op for %s", self.cfg.vault_path)
            self.ready = True
        except Exception as e:
            log.error("Obsidian Sync setup fejl: %s", e)

    def sync(self) -> None:
        if not self.ready:
            return
        try:
            res = self._run(["sync", "--path", self.cfg.vault_path])
            if res.returncode != 0:
                log.warning("Obsidian sync fejl: %s", (res.stderr or res.stdout).strip()[-300:])
        except Exception as e:
            log.warning("Obsidian sync fejl: %s", e)
