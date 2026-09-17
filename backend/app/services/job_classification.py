from typing import Any


_ENGAGEMENT_LABELS = {
    "contract": "contract",
    "contractor": "contract",
    "contract to hire": "contract_to_hire",
    "contract-to-hire": "contract_to_hire",
    "c2h": "contract_to_hire",
    "c2c": "c2c",
    "corp to corp": "c2c",
    "w2": "w2",
    "full time": "full_time",
    "full-time": "full_time",
    "fulltime": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "internship": "internship",
    "intern": "internship",
}


def classify_engagement(*values: Any) -> str | None:
    """Normalize an engagement label only when the source explicitly supplies it."""
    for value in values:
        if value is None:
            continue
        label = str(value).strip()
        if not label:
            continue
        normalized = _ENGAGEMENT_LABELS.get(label.lower())
        return normalized or label
    return None