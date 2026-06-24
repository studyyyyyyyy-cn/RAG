"""Custom exception hierarchy for clear error diagnosis."""


# ── Base ──────────────────────────────────────────────────────────────────

class RAGProError(Exception):
    """Base exception for all RAG-Pro errors."""
    pass


# ── Vector Store ──────────────────────────────────────────────────────────

class VectorStoreError(RAGProError):
    """Base for vector store errors."""
    pass


class CollectionNotFoundError(VectorStoreError):
    """Milvus collection does not exist."""
    def __init__(self, collection_name: str):
        super().__init__(f"向量集合不存在: {collection_name}")
        self.collection_name = collection_name


class DimensionMismatchError(VectorStoreError):
    """Embedding dimension does not match collection schema."""
    def __init__(self, embedder_dim: int, collection_dim: int | None, model: str):
        super().__init__(
            f"向量维度不匹配: Embedder({model})输出{embedder_dim}维, "
            f"Collection为{collection_dim}维。请调用 /repair-collection 修复"
        )
        self.embedder_dim = embedder_dim
        self.collection_dim = collection_dim


class VectorInsertError(VectorStoreError):
    """Failed to insert vectors into Milvus."""
    def __init__(self, detail: str):
        super().__init__(f"向量写入失败: {detail}")


class VectorSearchError(VectorStoreError):
    """Failed to search vectors in Milvus."""
    def __init__(self, detail: str):
        super().__init__(f"向量检索失败: {detail}")


class MilvusNotAvailableError(VectorStoreError):
    """Milvus service is unreachable, using in-memory fallback."""
    def __init__(self, detail: str = ""):
        hint = "（已降级为内存向量存储）" if detail else ""
        super().__init__(f"Milvus不可用{hint}: {detail}")


# ── Graph Store ───────────────────────────────────────────────────────────

class GraphStoreError(RAGProError):
    """Base for graph store errors."""
    pass


class Neo4jNotConnectedError(GraphStoreError):
    """Neo4j database is not reachable."""
    def __init__(self):
        super().__init__(
            "Neo4j图数据库未连接。请确保: 1) Neo4j已启动(bolt://localhost:7687) "
            "2) pip install neo4j 已安装 3) 重启后端"
        )


class EntityNotFoundError(GraphStoreError):
    """Requested entity not found in Neo4j."""
    def __init__(self, entity_id: str):
        super().__init__(f"图谱实体不存在: {entity_id}")


class GraphBuildError(GraphStoreError):
    """Graph construction failed."""
    def __init__(self, detail: str):
        super().__init__(f"图谱构建失败: {detail}")


# ── Embedding ─────────────────────────────────────────────────────────────

class EmbedderError(RAGProError):
    """Base for embedding errors."""
    pass


class ModelLoadError(EmbedderError):
    """Failed to load embedding model."""
    def __init__(self, model_name: str, detail: str = ""):
        hint = " 请检查模型是否已下载到 backend/models/ 目录" if detail else ""
        super().__init__(f"模型加载失败: {model_name}{hint}. {detail}")
        self.model_name = model_name


class EmbeddingError(EmbedderError):
    """Failed to embed text batch."""
    def __init__(self, batch_size: int, detail: str = ""):
        super().__init__(f"文本嵌入失败(批次大小{batch_size}): {detail}")


# ── Entity Extraction ─────────────────────────────────────────────────────

class ExtractionError(RAGProError):
    """Base for entity extraction errors."""
    pass


class LLMExtractionError(ExtractionError):
    """LLM call for entity extraction failed."""
    def __init__(self, detail: str):
        super().__init__(f"LLM实体抽取调用失败: {detail}")


class EmptyExtractionError(ExtractionError):
    """No entities extracted from text."""
    def __init__(self, text_preview: str = ""):
        preview = text_preview[:50] + "..." if len(text_preview) > 50 else text_preview
        super().__init__(f"文本中未抽取到实体: {preview}")


# ── Document Pipeline ─────────────────────────────────────────────────────

class DocumentProcessError(RAGProError):
    """Base for document processing errors."""
    pass


class ParseError(DocumentProcessError):
    """Document parsing failed."""
    def __init__(self, filename: str, detail: str = ""):
        super().__init__(f"文档解析失败({filename}): {detail}")
        self.filename = filename


class ChunkError(DocumentProcessError):
    """Document chunking failed."""
    def __init__(self, detail: str):
        super().__init__(f"文档分块失败: {detail}")


class EmptyDocumentError(DocumentProcessError):
    """No content extracted from document."""
    def __init__(self, filename: str):
        super().__init__(f"文档无内容可提取({filename})，可能是扫描版PDF或加密文件")


# ── LLM ───────────────────────────────────────────────────────────────────

class LLMConfigError(RAGProError):
    """LLM configuration issue."""
    pass


class NoLLMConfiguredError(LLMConfigError):
    """No LLM provider configured."""
    def __init__(self):
        super().__init__("未配置LLM模型，请先在「系统设置」中添加模型")


class LLMCallError(LLMConfigError):
    """LLM API call failed."""
    def __init__(self, provider: str, detail: str = ""):
        super().__init__(f"LLM调用失败({provider}): {detail}")
        self.provider = provider
