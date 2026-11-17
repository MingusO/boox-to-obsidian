import json
import logging
import os
import urllib.request

log = logging.getLogger("notify")


class Notifier:
    """Sender besked via Home Assistant (kraever homeassistant_api i add on'et)."""

    def __init__(self, service: str):
        self.service = service.replace("notify.", "", 1).strip() if service else ""

    def send(self, title: str, message: str) -> None:
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not self.service or not token:
            return
        req = urllib.request.Request(
            f"http://supervisor/core/api/services/notify/{self.service}",
            data=json.dumps({"title": title, "message": message}).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            log.warning("Notifikation fejlede: %s", e)


class NullNotifier:
    def send(self, title: str, message: str) -> None:
        pass
