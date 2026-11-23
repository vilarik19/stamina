from __future__ import annotations

import random


def generate_practice_text(allowed_chars: str, word_count: int = 25, *, seed: int | None = None) -> str:
    rng = random.Random(seed)
    allowed = [c for c in allowed_chars if c]
    if not allowed:
        return ""

    words: list[str] = []
    for _ in range(max(1, int(word_count))):
        length = rng.randint(3, 8)
        word = "".join(rng.choice(allowed) for _ in range(length)).strip()
        word = word if word else rng.choice(allowed).strip() or " "
        words.append(word)
    return " ".join(words).strip()

