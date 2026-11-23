from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-]+")


def sanitize_username(username: str) -> str:
    name = (username or "").strip()
    name = _SAFE_NAME_RE.sub("_", name)
    name = name.strip("_")
    return name or "user"


@dataclass(frozen=True)
class User:
    username: str


class UserStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "users.json"

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"users": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"users": []}

    def list_users(self) -> List[User]:
        data = self.load()
        users = []
        for u in data.get("users", []):
            if isinstance(u, str) and u.strip():
                users.append(User(u.strip()))
        users.sort(key=lambda x: x.username.lower())
        return users

    def add_user(self, username: str) -> User:
        username = sanitize_username(username)
        data = self.load()
        existing = {u for u in data.get("users", []) if isinstance(u, str)}
        if username not in existing:
            data["users"] = sorted(list(existing | {username}), key=str.lower)
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return User(username=username)

