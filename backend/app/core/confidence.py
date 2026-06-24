"""Confidence scoring for retrieval quality assessment."""


def compute_confidence(rerank_scores: list[float], threshold: float = 0.3) -> float:
    """Compute a confidence score from reranker scores.

    Strategy:
    - Average the top scores
    - Apply a penalty if the top score is below threshold
    - Return a value between 0.0 and 1.0
    """
    if not rerank_scores:
        return 0.0

    top_score = max(rerank_scores)
    avg_score = sum(rerank_scores) / len(rerank_scores)

    # Weighted: top score matters most
    confidence = 0.6 * top_score + 0.4 * avg_score

    # Clamp to [0, 1]
    return max(0.0, min(1.0, confidence))


def confidence_label(score: float) -> str:
    """Return a human-readable confidence label."""
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    elif score >= 0.3:
        return "low"
    return "very_low"
