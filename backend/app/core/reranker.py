"""Cross-Encoder reranker for improving retrieval precision.

Uses bge-reranker-v2-m3 by default: free, open-source, Chinese+English.
"""

import logging
import os

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-Encoder reranker that scores query-passage relevance."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", device: str = "cpu"):
        self.model = None
        self.model_name = model_name
        self.device = device
        self._initialized = False

    def _ensure_model(self):
        """Lazy load the reranker model. Allows retry if previous attempt failed."""
        if self._initialized and self.model is not None:
            return True
        if self._initialized and self.model is None:
            # Previous attempt failed — allow retry
            logger.info("Retrying reranker model load after previous failure")
            self._initialized = False

        # Check local model path
        from pathlib import Path
        local_model_path = Path(__file__).parent.parent.parent / "models" / "BAAI" / "bge-reranker-v2-m3"

        has_model = (local_model_path / "pytorch_model.bin").exists() or (local_model_path / "model.safetensors").exists()
        if local_model_path.exists() and has_model:
            logger.info(f"Loading reranker from local path: {local_model_path}")
            model_path = str(local_model_path)
        else:
            # Set HF mirror for China users
            if not os.environ.get('HF_ENDPOINT'):
                os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
            model_path = self.model_name
            logger.info(f"Loading reranker model: {model_path} on {self.device}")

        try:
            from FlagEmbedding import FlagReranker
            self.model = FlagReranker(model_path, use_fp16=(self.device != "cpu"))
            self._initialized = True
            logger.info("Reranker model loaded successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to load reranker model: {e}")
            self.model = None
            self._initialized = True  # Mark as attempted so we don't spam retries
            return False

    def rerank(
        self,
        query: str,
        passages: list[str],
        top_n: int = 5,
    ) -> list[tuple[int, float]]:
        """Rerank passages by relevance to query.

        Returns list of (original_index, score) sorted by score descending.
        """
        if not passages:
            return []

        # Ensure model is loaded
        if not self._ensure_model():
            # Fallback: return passages in original order with equal scores
            logger.warning("Reranker not available, using original order")
            return [(i, 1.0 - i * 0.1) for i in range(min(top_n, len(passages)))]

        pairs = [[query, passage] for passage in passages]
        scores = self.model.compute_score(pairs, normalize=True)

        # Ensure scores is a list
        if isinstance(scores, (int, float)):
            scores = [scores]

        # Sort by score descending and take top_n
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores[:top_n]


# Singleton cache
_reranker_cache: dict[str, Reranker] = {}


def get_reranker(model_name: str = "BAAI/bge-reranker-v2-m3", device: str = "cpu") -> Reranker:
    """Get or create a cached reranker instance."""
    cache_key = f"{model_name}:{device}"
    if cache_key not in _reranker_cache:
        _reranker_cache[cache_key] = Reranker(model_name, device)
    return _reranker_cache[cache_key]
