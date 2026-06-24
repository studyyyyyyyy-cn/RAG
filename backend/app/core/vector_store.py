"""Vector store abstraction with Milvus and in-memory fallback.

Uses Milvus Lite (file-based) for local development.
Falls back to in-memory FAISS-like search on Windows where Milvus Lite is unavailable.
"""
import logging
import os
import uuid
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


def _numpy_encoder(obj):
    """JSON encoder for numpy types."""
    import numpy as np
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64, np.float16)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64, np.int16, np.int8)):
        return int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# Ensure data directory exists
data_dir = Path(settings.MILVUS_URI).parent
data_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class SearchResult:
    """A single search result from vector store."""
    chunk_id: str
    score: float
    content: str | None = None


class InMemoryVectorStore:
    """Simple in-memory vector store using numpy for similarity search."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path).parent / "vectors.json"
        self.collections: dict[str, dict] = {}  # collection_name -> {vectors, metadata}
        self._dirty = False
        self._load_from_disk()

    def _load_from_disk(self):
        """Load vectors from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.collections = json.load(f)
                # Ensure backward compatibility - add sparse_vectors if missing
                for name, collection in self.collections.items():
                    if "sparse_vectors" not in collection:
                        collection["sparse_vectors"] = [{} for _ in collection.get("vectors", [])]
                logger.info(f"Loaded {len(self.collections)} collections from disk")
            except Exception as e:
                logger.warning(f"Failed to load vectors from disk: {e}")
                self.collections = {}

    def _save_to_disk(self):
        """Save vectors to disk."""
        if not self._dirty:
            return
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.collections, f, ensure_ascii=False, default=_numpy_encoder)
            self._dirty = False
        except Exception as e:
            logger.warning(f"Failed to save vectors to disk: {e}")

    def has_collection(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, name: str):
        if name not in self.collections:
            self.collections[name] = {"vectors": [], "sparse_vectors": [], "metadata": []}
            self._dirty = True
            self._save_to_disk()
            logger.info(f"Created in-memory collection: {name}")

    def insert(self, name: str, data: list[dict]):
        if name not in self.collections:
            self.collections[name] = {"vectors": [], "sparse_vectors": [], "metadata": []}

        for item in data:
            self.collections[name]["vectors"].append(item["dense_vector"])
            # Store sparse vector as dict (deserialize from JSON string if needed)
            sparse_vec = item.get("sparse_vector", {})
            if isinstance(sparse_vec, str) and sparse_vec:
                try:
                    sparse_vec = json.loads(sparse_vec)
                except (json.JSONDecodeError, TypeError):
                    sparse_vec = {}
            self.collections[name]["sparse_vectors"].append(sparse_vec)
            self.collections[name]["metadata"].append({
                "id": item["id"],
                "chunk_id": item["chunk_id"],
                "doc_id": item["doc_id"],
                "content": item["content"],
            })

        self._dirty = True
        self._save_to_disk()
        logger.info(f"Inserted {len(data)} vectors into {name}")

    def search(self, name: str, query_vector: list, top_k: int = 20) -> list[dict]:
        if name not in self.collections:
            return []

        collection = self.collections[name]
        if not collection["vectors"]:
            return []

        # Convert to numpy arrays
        vectors = np.array(collection["vectors"])
        query = np.array(query_vector)

        # Normalize for cosine similarity
        vectors_norm = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10)
        query_norm = query / (np.linalg.norm(query) + 1e-10)

        # Compute cosine similarity
        similarities = np.dot(vectors_norm, query_norm)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "id": collection["metadata"][idx]["id"],
                "chunk_id": collection["metadata"][idx]["chunk_id"],
                "doc_id": collection["metadata"][idx]["doc_id"],
                "content": collection["metadata"][idx]["content"],
                "score": float(similarities[idx]),
            })

        return results

    def sparse_search(self, name: str, query_sparse: dict, top_k: int = 20) -> list[dict]:
        """Perform sparse vector search (BM25-style keyword matching)."""
        if name not in self.collections:
            return []

        collection = self.collections[name]
        if not collection["sparse_vectors"]:
            return []

        # Calculate sparse similarity scores
        scores = []
        for idx, doc_sparse in enumerate(collection["sparse_vectors"]):
            if not doc_sparse:
                scores.append(0.0)
                continue

            # Compute overlap score between query and document sparse vectors
            score = 0.0
            for token_id, query_weight in query_sparse.items():
                if str(token_id) in doc_sparse:
                    doc_weight = doc_sparse[str(token_id)]
                    score += query_weight * doc_weight
            scores.append(score)

        # Get top-k indices
        scores_array = np.array(scores)
        top_indices = np.argsort(scores_array)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores_array[idx] > 0:  # Only include non-zero scores
                results.append({
                    "id": collection["metadata"][idx]["id"],
                    "chunk_id": collection["metadata"][idx]["chunk_id"],
                    "doc_id": collection["metadata"][idx]["doc_id"],
                    "content": collection["metadata"][idx]["content"],
                    "score": float(scores_array[idx]),
                })

        return results

    def hybrid_search(self, name: str, dense_query: list, sparse_query: dict | None = None, top_k: int = 20) -> list[dict]:
        """Perform hybrid search using RRF (Reciprocal Rank Fusion)."""
        if name not in self.collections:
            return []

        # Perform dense search
        dense_results = self.search(name, dense_query, top_k * 2)  # Get more candidates

        # Perform sparse search if available
        sparse_results = []
        if sparse_query:
            sparse_results = self.sparse_search(name, sparse_query, top_k * 2)

        # If no sparse results, return dense only
        if not sparse_results:
            return dense_results[:top_k]

        # RRF fusion
        k = 60  # RRF constant
        rrf_scores = {}

        # Add dense scores
        for rank, result in enumerate(dense_results, 1):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank)

        # Add sparse scores
        for rank, result in enumerate(sparse_results, 1):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank)

        # Create result map for metadata
        result_map = {}
        for result in dense_results + sparse_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by RRF score
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Build final results
        final_results = []
        for chunk_id, rrf_score in sorted_chunks[:top_k]:
            result = result_map[chunk_id].copy()
            result["score"] = rrf_score
            final_results.append(result)

        return final_results

    def delete(self, name: str, filter_expr: str):
        """Delete vectors matching filter (simplified - only supports doc_id filter)."""
        if name not in self.collections:
            return

        # Parse filter expression like 'doc_id == "xxx"'
        import re
        match = re.search(r'doc_id\s*==\s*"([^"]+)"', filter_expr)
        if match:
            doc_id = match.group(1)
            collection = self.collections[name]
            new_vectors = []
            new_sparse_vectors = []
            new_metadata = []
            deleted = 0
            sparse_vecs = collection.get("sparse_vectors", [])
            for i, meta in enumerate(collection["metadata"]):
                if meta["doc_id"] != doc_id:
                    new_vectors.append(collection["vectors"][i])
                    # Ensure sparse_vectors stays aligned with vectors
                    if i < len(sparse_vecs):
                        new_sparse_vectors.append(sparse_vecs[i])
                    else:
                        new_sparse_vectors.append({})
                    new_metadata.append(meta)
                else:
                    deleted += 1

            collection["vectors"] = new_vectors
            collection["sparse_vectors"] = new_sparse_vectors
            collection["metadata"] = new_metadata
            self._save_to_disk()
            logger.info(f"Deleted {deleted} vectors for doc {doc_id} from {name}")

    def drop_collection(self, name: str):
        if name in self.collections:
            del self.collections[name]
            self._save_to_disk()
            logger.info(f"Dropped collection {name}")


class VectorStore:
    """Vector store supporting dense vector search with Milvus or in-memory fallback."""

    DENSE_DIM = 1024  # BGE-M3 embedding dimension

    def __init__(self):
        self.client = None
        self._use_memory = False
        self._init_client()

    @classmethod
    def _detect_dim(cls, embedder=None) -> int:
        """Dynamically detect embedding dimension from embedder if available."""
        if embedder and hasattr(embedder, "dim"):
            return embedder.dim
        return cls.DENSE_DIM

    def _init_client(self):
        """Initialize Milvus client or fall back to in-memory store."""
        if self.client is not None:
            return True

        # Try Milvus first
        try:
            from pymilvus import MilvusClient
            self.client = MilvusClient(uri=settings.MILVUS_URI)
            logger.info(f"Milvus client initialized with uri: {settings.MILVUS_URI}")
            return True
        except Exception as e:
            logger.warning(f"Milvus not available ({e}), using in-memory vector store")
            self._use_memory = True
            self.client = InMemoryVectorStore(settings.MILVUS_URI)
            return True

    def _collection_name(self, kb_id: str) -> str:
        """Generate a collection name from knowledge base ID."""
        return f"kb_{kb_id.replace('-', '_')}"

    def create_collection(self, kb_id: str, dense_dim: int | None = None, force: bool = False):
        """Create or verify a collection for a knowledge base.

        Automatically detects dimension mismatches and recreates the collection.
        Use force=True to always recreate.
        """
        if dense_dim is None:
            dense_dim = self.DENSE_DIM
        self._init_client()
        if self.client is None:
            logger.warning("Vector store not available")
            return

        collection_name = self._collection_name(kb_id)

        if self._use_memory:
            self.client.create_collection(collection_name)
            return

        if self.client.has_collection(collection_name) and not force:
            existing_dim = self._get_collection_dim(collection_name)
            if existing_dim is None:
                # Can't determine dimension — recreate to be safe
                logger.warning(
                    f"Cannot read dimension of {collection_name}, "
                    f"recreating with dim={dense_dim}"
                )
                self.client.drop_collection(collection_name)
            elif existing_dim != dense_dim:
                logger.warning(
                    f"Collection {collection_name} dim mismatch: "
                    f"existing={existing_dim}, required={dense_dim}. Recreating..."
                )
                self.client.drop_collection(collection_name)
            else:
                logger.info(f"Collection {collection_name} OK (dim={existing_dim})")
                return

        # Also drop if force=True
        if force and self.client.has_collection(collection_name):
            self.client.drop_collection(collection_name)
            logger.info(f"Force-dropped collection {collection_name}")

        from pymilvus import DataType
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=dense_dim)
        schema.add_field(field_name="sparse_vector", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=8192)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="dense_vector", index_type="FLAT", metric_type="COSINE")

        self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
        logger.info(f"Created collection {collection_name} with dim={dense_dim}")

    def _get_collection_dim(self, collection_name: str) -> int | None:
        """Read the dense_vector dimension from an existing Milvus collection."""
        try:
            info = self.client.describe_collection(collection_name)
            # Milvus Lite returns fields as a list; Milvus server may differ
            fields = info.get("fields", [])
            if not fields and hasattr(info, "schema"):
                fields = info.schema.get("fields", [])
            for field in fields:
                name = field.get("name", "") if isinstance(field, dict) else getattr(field, "name", "")
                if name == "dense_vector":
                    if isinstance(field, dict):
                        return field.get("params", {}).get("dim") or field.get("dim")
                    else:
                        return getattr(field, "params", {}).get("dim") or getattr(field, "dim", None)
        except Exception as e:
            logger.warning(f"Cannot read collection dim for {collection_name}: {e}")
        return None

    def insert(
        self,
        kb_id: str,
        chunk_ids: list[str],
        doc_ids: list[str],
        dense_vectors: list,
        sparse_vectors: list | None,
        contents: list[str],
    ):
        """Insert chunk vectors."""
        self._init_client()
        if self.client is None:
            logger.warning("Vector store not available, skipping insert")
            return

        collection_name = self._collection_name(kb_id)

        data = []
        for i in range(len(chunk_ids)):
            item = {
                "id": str(uuid.uuid4()),
                "chunk_id": chunk_ids[i],
                "doc_id": doc_ids[i],
                "dense_vector": dense_vectors[i].tolist() if hasattr(dense_vectors[i], 'tolist') else dense_vectors[i],
                "sparse_vector": "" if not sparse_vectors or i >= len(sparse_vectors) else json.dumps(sparse_vectors[i], default=_numpy_encoder),
                "content": contents[i][:8000],
            }
            data.append(item)

        if self._use_memory:
            self.client.insert(collection_name, data)
        else:
            self.client.insert(collection_name=collection_name, data=data)
            logger.info(f"Inserted {len(data)} vectors into {collection_name}")

    def hybrid_search(
        self,
        kb_id: str,
        dense_query,
        sparse_query: dict | None = None,
        top_k: int = 20,
    ) -> list[SearchResult]:
        """Perform hybrid search (dense + sparse with RRF fusion)."""
        self._init_client()
        if self.client is None:
            logger.warning("Vector store not available")
            return []

        collection_name = self._collection_name(kb_id)

        if self._use_memory:
            # Use in-memory hybrid search with RRF
            dense_vec = dense_query.tolist() if hasattr(dense_query, 'tolist') else dense_query
            results = self.client.hybrid_search(collection_name, dense_vec, sparse_query, top_k)
            return [SearchResult(chunk_id=r["chunk_id"], score=r["score"], content=r["content"]) for r in results]

        if not self.client.has_collection(collection_name):
            return []

        # For Milvus, use dense search only (Milvus Lite doesn't support sparse vectors well)
        results = self.client.search(
            collection_name=collection_name,
            data=[dense_query.tolist() if hasattr(dense_query, 'tolist') else dense_query],
            anns_field="dense_vector",
            search_params={"metric_type": "COSINE"},
            limit=top_k,
            output_fields=["chunk_id", "content", "doc_id"],
        )

        search_results = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                search_results.append(SearchResult(
                    chunk_id=entity.get("chunk_id", ""),
                    score=hit.get("distance", 0.0),
                    content=entity.get("content", ""),
                ))

        return search_results

    def delete_by_doc(self, kb_id: str, doc_id: str):
        """Delete all vectors belonging to a document."""
        self._init_client()
        if self.client is None:
            return

        collection_name = self._collection_name(kb_id)

        if self._use_memory:
            self.client.delete(collection_name, f'doc_id == "{doc_id}"')
        elif self.client.has_collection(collection_name):
            self.client.delete(collection_name=collection_name, filter=f'doc_id == "{doc_id}"')
            logger.info(f"Deleted vectors for doc {doc_id}")

    def drop_collection(self, kb_id: str):
        """Drop the entire collection for a knowledge base."""
        self._init_client()
        if self.client is None:
            return

        collection_name = self._collection_name(kb_id)

        if self._use_memory:
            self.client.drop_collection(collection_name)
        elif self.client.has_collection(collection_name):
            self.client.drop_collection(collection_name)
            logger.info(f"Dropped collection {collection_name}")


# Singleton
vector_store = VectorStore()
