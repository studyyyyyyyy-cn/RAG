"""Embedding abstraction layer.

Default: BGE-M3 (produces both dense and sparse vectors in a single pass).
Supports switching to other models via configuration.
"""

import logging
import os
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Return the embedding dimension."""
        ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> dict:
        """Embed a batch of documents. Returns dict with 'dense' and optionally 'sparse' keys."""
        ...

    @abstractmethod
    def embed_query(self, text: str) -> dict:
        """Embed a single query."""
        ...


class DummyEmbedder(BaseEmbedder):
    """Dummy embedder for testing - returns random vectors."""

    def __init__(self, dim: int = 1024):
        self._dim = dim
        logger.warning("Using DummyEmbedder - for testing only!")

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> dict:
        """Return random dense vectors."""
        import numpy as np
        return {
            "dense": np.random.randn(len(texts), self.dim).astype(np.float32),
        }

    def embed_query(self, text: str) -> dict:
        """Return random dense vector."""
        import numpy as np
        return {
            "dense": np.random.randn(self.dim).astype(np.float32),
        }


class BGEM3Embedder(BaseEmbedder):
    """BGE-M3 embedder — produces dense + sparse vectors in one forward pass."""

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu", batch_size: int = 32):
        from FlagEmbedding import BGEM3FlagModel
        from pathlib import Path
        
        # Check local model path first
        local_model_path = Path(__file__).parent.parent.parent / "models" / "BAAI" / "bge-m3"
        
        if local_model_path.exists() and (local_model_path / "pytorch_model.bin").exists():
            logger.info(f"Loading BGE-M3 from local path: {local_model_path}")
            model_path = str(local_model_path)
        else:
            # Set HF mirror for China users
            if not os.environ.get('HF_ENDPOINT'):
                os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
            logger.info(f"Loading BGE-M3 model: {model_name} on {device}")
            model_path = model_name
            
        self.model = BGEM3FlagModel(model_path, use_fp16=(device != "cpu"))
        self.batch_size = batch_size

    @property
    def dim(self) -> int:
        return 1024

    def embed_documents(self, texts: list[str]) -> dict:
        """Embed documents returning both dense and sparse vectors."""
        output = self.model.encode(
            texts,
            batch_size=self.batch_size,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return {
            "dense": output["dense_vecs"],    # np.ndarray shape (n, 1024)
            "sparse": output["lexical_weights"],  # list of dicts {token_id: weight}
        }

    def embed_query(self, text: str) -> dict:
        """Embed a single query."""
        output = self.model.encode(
            [text],
            batch_size=1,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return {
            "dense": output["dense_vecs"][0],      # np.ndarray shape (1024,)
            "sparse": output["lexical_weights"][0],  # dict {token_id: weight}
        }


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding model (e.g., text-embedding-3-large)."""

    # OpenAI embedding dimensions mapping
    _DIMS = {
        "text-embedding-3-large": 3072,
        "text-embedding-3-small": 1536,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model_name: str = "text-embedding-3-large", api_key: str = ""):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    @property
    def dim(self) -> int:
        return self._DIMS.get(self.model_name, 1536)

    def embed_documents(self, texts: list[str]) -> dict:
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        dense = np.array([item.embedding for item in response.data])
        return {"dense": dense}

    def embed_query(self, text: str) -> dict:
        response = self.client.embeddings.create(input=[text], model=self.model_name)
        return {"dense": np.array(response.data[0].embedding)}


class SentenceTransformerEmbedder(BaseEmbedder):
    """Lightweight embedder using sentence-transformers (auto-downloads small models)."""

    def __init__(self, model_name: str = "paraphrase-MiniLM-L6-v2", device: str = "cpu"):
        from sentence_transformers import SentenceTransformer
        from pathlib import Path
        
        # 检查本地模型路径 (支持 .bin 和 .safetensors 格式)
        local_model_path = Path(__file__).parent.parent.parent / "models" / model_name
        
        has_model = False
        if local_model_path.exists():
            # 检查是否存在模型文件 (.bin, .safetensors, .pt)
            has_model = any(local_model_path.glob("*.bin")) or \
                        any(local_model_path.glob("*.safetensors")) or \
                        any(local_model_path.glob("*.pt"))
        
        if local_model_path.exists() and has_model:
            logger.info(f"Loading SentenceTransformer from local path: {local_model_path}")
            model_path = str(local_model_path)
        else:
            logger.info(f"Loading SentenceTransformer model: {model_name} on {device}")
            model_path = model_name
        
        self.model = SentenceTransformer(model_path, device=device)
        self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> dict:
        """Embed documents using sentence-transformers."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return {
            "dense": embeddings,
        }

    def embed_query(self, text: str) -> dict:
        """Embed a single query."""
        embedding = self.model.encode([text], convert_to_numpy=True)[0]
        return {
            "dense": embedding,
        }


# Factory
_embedder_cache: dict[str, BaseEmbedder] = {}


def get_embedder(model_name: str = "BAAI/bge-m3", device: str = "cpu", **kwargs) -> BaseEmbedder:
    """Get or create a cached embedder instance."""
    cache_key = f"{model_name}:{device}"
    if cache_key not in _embedder_cache:
        # Check if we should use lightweight model (for quick testing without downloading BGE-M3)
        use_lightweight = os.environ.get('USE_LIGHTWEIGHT_EMBEDDER', '0') == '1'
        
        if use_lightweight:
            logger.info("Using lightweight embedder (USE_LIGHTWEIGHT_EMBEDDER=1)")
            _embedder_cache[cache_key] = SentenceTransformerEmbedder("paraphrase-MiniLM-L6-v2", device)
        elif "bge-m3" in model_name.lower():
            _embedder_cache[cache_key] = BGEM3Embedder(model_name, device)
        elif "openai" in model_name.lower() or "text-embedding" in model_name.lower():
            _embedder_cache[cache_key] = OpenAIEmbedder(model_name, kwargs.get("api_key", ""))
        else:
            # Default to sentence-transformers for other models
            _embedder_cache[cache_key] = SentenceTransformerEmbedder(model_name, device)
    return _embedder_cache[cache_key]
