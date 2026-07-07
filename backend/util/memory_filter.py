import re

from backend.util.memory import classify_memory_type

_FILLER_ONLY = re.compile(
    r"^(hey|hi|hello|ok|okay|thanks|thank you|yes|no|yep|nope|sure|cool|bye|lol|haha)[\s!?.]*$",
    re.IGNORECASE,
)


def is_memory_worthy(text: str) -> bool:
    content = text.strip()
    if not content:
        return False

    if len(content) < 20:
        return False

    if _FILLER_ONLY.match(content):
        return False

    detected_type, confidence = classify_memory_type(content, requested_type="auto")
    if detected_type in {"goal", "preference", "event", "style"} and confidence >= 0.7:
        return True

    return len(content) > 60
