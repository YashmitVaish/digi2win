import re

MEMORY_TYPES = {"fact", "preference", "event", "goal", "style"}

_GOAL_HINTS = re.compile(
    r"\b(goal|aim|plan|target|i want to|i need to|i will|trying to|aspire|objective)\b",
    re.IGNORECASE,
)
_PREFERENCE_HINTS = re.compile(
    r"\b(i like|i love|i prefer|favorite|i dislike|i hate|i enjoy |i prefer)\b",
    re.IGNORECASE,
)
_EVENT_HINTS = re.compile(
    r"\b(yesterday|today|last|this morning|this week|on monday|on tuesday|on wednesday|on thursday|on friday|on saturday|on sunday|met|went|happened|attended|visited|missed)\b",
    re.IGNORECASE,
)
_STYLE_HINTS = re.compile(
    r"\b(when you respond|respond to me|tone|style|bullet points|format|numbered action items|start with|end with)\b",
    re.IGNORECASE,
)

_EMOTION_POS = re.compile(r"\b(love|excited|happy|grateful|proud|correct)\b", re.IGNORECASE)
_EMOTION_NEG = re.compile(r"\b(stressed|anxious|sad|angry|worried|upset|fuck|shit)\b", re.IGNORECASE)


def classify_memory_type(text: str, requested_type: str = "auto") -> tuple[str, float]:
    if requested_type in MEMORY_TYPES:
        return requested_type, 1.0

    if _GOAL_HINTS.search(text):
        return "goal", 0.74
    if _PREFERENCE_HINTS.search(text):
        return "preference", 0.72
    if _EVENT_HINTS.search(text):
        return "event", 0.7
    if _STYLE_HINTS.search(text):
        return "style", 0.78
    return "fact", 0.62


def emotional_weight(text: str) -> float:
    positive = len(_EMOTION_POS.findall(text))
    negative = len(_EMOTION_NEG.findall(text))
    weight = 0.08 * (positive + negative)
    return min(weight, 0.4)


def query_type_boost(query: str, memory_type: str) -> float:
    query_l = query.lower()
    target = "fact"

    if _GOAL_HINTS.search(query_l):
        target = "goal"
    elif _PREFERENCE_HINTS.search(query_l) or "preference" in query_l:
        target = "preference"
    elif _EVENT_HINTS.search(query_l) or "recent" in query_l:
        target = "event"
    elif _STYLE_HINTS.search(query_l):
        target = "style"

    if memory_type == target:
        return 1.25
    if memory_type == "fact":
        return 1.0
    return 0.93
