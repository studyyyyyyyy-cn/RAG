"""Application configuration management."""

import base64
import hashlib
import os
from pathlib import Path
from typing import Optional, Union

from pydantic_settings import BaseSettings

# 设置 Hugging Face 模型本地目录
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
os.environ['HF_HOME'] = str(MODELS_DIR)
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# Ensure data dir exists for SQLite path construction
_data_dir = Path(__file__).parent.parent / "data"
_data_dir.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "RAG Knowledge Base"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database (SQLite for local dev, PostgreSQL for production)
    DATABASE_URL: str = "sqlite+aiosqlite:///" + (_data_dir / "ragapp.db").as_posix()
    DATABASE_ECHO: bool = False

    # Redis (optional, not required for local dev)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Milvus (Milvus Lite file mode for local dev, server mode for production)
    MILVUS_URI: str = (_data_dir / "milvus.db").as_posix()
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_DB: str = "default"

    # File Upload
    UPLOAD_DIR: str = str(Path(__file__).parent.parent / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: tuple = ("pdf", "csv", "txt", "md", "docx", "doc")

    # Embedding Model
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"  # cpu / cuda
    EMBEDDING_BATCH_SIZE: int = 32

    # Local Model Path (optional - place models here to use offline)
    LOCAL_MODEL_DIR: str = str(Path(__file__).parent.parent / "models")

    # Reranker Model
    DEFAULT_RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Retrieval
    RETRIEVAL_TOP_K: int = 20  # Hybrid search candidates
    RERANK_TOP_N: int = 5      # After reranking
    CONFIDENCE_THRESHOLD: float = 0.3

    # Chunking
    DEFAULT_CHUNK_SIZE: int = 512
    DEFAULT_CHUNK_OVERLAP: int = 64
    PARENT_CHUNK_SIZE: int = 1536

    # Neo4j (Knowledge Graph)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    GRAPH_ENABLED: bool = True

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Security
    SECRET_KEY: str = "change-this-to-a-secure-random-string"
    API_KEY_ENCRYPTION_KEY: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}

    def model_post_init(self, __context):
        """Validate configuration on startup."""
        super().model_post_init(__context)
        if not self.DEBUG and self.SECRET_KEY == "change-this-to-a-secure-random-string":
            import warnings
            warnings.warn(
                "SECRET_KEY is using the default value. Set a secure random string in production.",
                RuntimeWarning,
            )


settings = Settings()


# ── API Key encryption utilities ──────────────────────────────────────────

def _get_fernet():
    """Build a Fernet cipher from SECRET_KEY (deterministic per key)."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        # Fallback: base64 encode (NOT real encryption, but better than plaintext)
        return None
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_api_key(raw: str) -> str:
    """Encrypt an API key for storage. Returns prefixed ciphertext."""
    if not raw:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        # No cryptography library — store with prefix indicating plaintext
        return f"plain:{raw}"
    return f"enc:{fernet.encrypt(raw.encode()).decode()}"


def decrypt_api_key(encrypted: Optional[str]) -> str:
    """Decrypt a stored API key. Returns original plaintext."""
    if not encrypted:
        return ""
    if encrypted.startswith("enc:"):
        fernet = _get_fernet()
        if fernet is None:
            return encrypted  # shouldn't happen but be safe
        try:
            return fernet.decrypt(encrypted[4:].encode()).decode()
        except Exception:
            return encrypted  # decryption failed, return as-is
    if encrypted.startswith("plain:"):
        return encrypted[6:]
    # Legacy: no prefix, assume plaintext
    return encrypted
