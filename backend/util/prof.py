import re
from sqlalchemy.orm import Session

def extract_profile_facts(user_message: str, db: Session):
    patterns = {
        "name": r"my name is\s+([A-Za-z][A-Za-z\- ]{1,40}?)(?:\s+and|[.,;!?]|$)",
        "role": r"i(?:'m| am)\s+(?:an?\s+)?([a-z][a-z\- ]{2,40}?)(?:\s+and|[.,;!?]|$)",
        "location": r"i(?:'m| am)\s+in\s+([A-Za-z][A-Za-z\- ]{1,40})",
        "school": r"i\s+(?:study at|go to|attend)\s+([A-Za-z0-9 .\-]{2,50})",
        "relationship": r"(?:my girlfriend|my boyfriend|my partner)\s+(?:is\s+)?([A-Za-z][A-Za-z\- ]{1,40})",
        "project": r"(?:working on|building)\s+([A-Za-z0-9 .\-]{2,40})",
    }
    updated = False
    for key, pattern in patterns.items():
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            value = _clean_value(match.group(1))
            if value:
                upsert_profile(db, key, value)
                updated = True
    if updated:
        db.commit()

def upsert_profile(db: Session, key: str, value: str):
    from datetime import datetime
    from backend.db.db import Profile

    row = db.query(Profile).filter(Profile.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(Profile(key=key, value=value))


def _clean_value(value: str) -> str:
    cleaned = value.strip().strip(".!,;:")
    lowered = cleaned.lower()
    if lowered in {"a", "an", "the"}:
        return ""
    return cleaned
