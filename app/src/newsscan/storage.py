"""Local file storage for uploaded scans.

Files are saved under random hex names, never under the name the user supplied, so a hostile
filename cannot escape the storage directory. Keys are validated again on every read.
"""

import re
import uuid
from pathlib import Path

_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ValueError("invalid storage key")
        return self.root / key[:2] / key

    def save(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)  # atomic on the same filesystem
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
