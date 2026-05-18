def score_to_label(score: float) -> str:
    """Map numeric occupancy score to categorical label."""
    if score < 40:
        return "NOT_FULL"
    elif score < 75:
        return "SEMI_FULL"
    else:
        return "FULL"

def label_to_score(label: str) -> int:
    """Map categorical label to a default numeric score."""
    mapping = {
        "NOT_FULL": 20,
        "SEMI_FULL": 55,
        "FULL": 90
    }
    return mapping.get(label, 50)
