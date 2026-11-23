from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stamina.core.metrics import TypingResult


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class Attempt:
    timestamp_utc: str
    mode: str  # lesson|practice
    lesson_id: Optional[str]
    layout: str
    duration_sec: float
    typed_chars: int
    correct_chars: int
    errors: int


class ProgressStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "progress.json"

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"attempts": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"attempts": []}

    def add_attempt(
        self,
        *,
        mode: str,
        lesson_id: Optional[str],
        layout: str,
        result: TypingResult,
    ) -> None:
        data = self.load()
        attempts: List[Dict[str, Any]] = list(data.get("attempts", []))
        attempts.append(
            asdict(
                Attempt(
                    timestamp_utc=_now_iso(),
                    mode=mode,
                    lesson_id=lesson_id,
                    layout=layout,
                    duration_sec=float(result.duration_sec),
                    typed_chars=int(result.typed_chars),
                    correct_chars=int(result.correct_chars),
                    errors=int(result.errors),
                )
            )
        )
        data["attempts"] = attempts
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

