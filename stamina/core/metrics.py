from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypingResult:
    duration_sec: float
    typed_chars: int
    correct_chars: int
    errors: int

    @property
    def accuracy(self) -> float:
        if self.typed_chars <= 0:
            return 1.0
        return max(0.0, min(1.0, self.correct_chars / self.typed_chars))

    @property
    def cpm(self) -> float:
        if self.duration_sec <= 0:
            return 0.0
        return (self.typed_chars / self.duration_sec) * 60.0

    @property
    def wpm(self) -> float:
        # 1 word = 5 chars (common typing metric)
        if self.duration_sec <= 0:
            return 0.0
        return ((self.typed_chars / 5.0) / self.duration_sec) * 60.0


def compute_result(target_text: str, typed_text: str, duration_sec: float) -> TypingResult:
    typed_chars = len(typed_text)
    correct_chars = 0
    errors = 0
    for idx, ch in enumerate(typed_text):
        if idx >= len(target_text):
            errors += 1
            continue
        if ch == target_text[idx]:
            correct_chars += 1
        else:
            errors += 1

    return TypingResult(
        duration_sec=max(0.0, float(duration_sec)),
        typed_chars=typed_chars,
        correct_chars=correct_chars,
        errors=errors,
    )

