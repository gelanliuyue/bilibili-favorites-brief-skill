import json
from pathlib import Path
from typing import Optional, Dict

from app.services.secure_store import SecureStore


class CookieConfigManager:
    def __init__(
        self,
        filepath: str = "config/downloader.json",
        secure_store: Optional[SecureStore] = None,
    ):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.store = secure_store or SecureStore(self.path)

    def _read(self) -> Dict[str, Dict[str, str]]:
        encrypted = self.store.read()
        if encrypted:
            return encrypted
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                legacy = json.load(f)
        except Exception:
            return {}
        if not isinstance(legacy, dict) or legacy.get("version") == 1:
            return {}
        if legacy:
            self.store.write(legacy)
        return legacy

    def _write(self, data: Dict[str, Dict[str, str]]):
        self.store.write(data)

    def get(self, platform: str) -> Optional[str]:
        data = self._read()
        return data.get(platform, {}).get("cookie")

    def set(self, platform: str, cookie: str):
        data = self._read()
        data[platform] = {"cookie": cookie}
        self._write(data)

    def delete(self, platform: str):
        data = self._read()
        if platform in data:
            del data[platform]
            if data:
                self._write(data)
            else:
                self.store.delete()

    def list_all(self) -> Dict[str, str]:
        data = self._read()
        return {k: v.get("cookie", "") for k, v in data.items()}

    def exists(self, platform: str) -> bool:
        return self.get(platform) is not None
