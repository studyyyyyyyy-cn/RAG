"""Knowledge graph builder: orchestrates entity extraction and Neo4j population.

Pipeline: chunks → entity extraction → entity dedup → Neo4j insert.
Also links chunks to entities via :MENTIONS relationships.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entity_extractor import (
    extract_entities_batch,
    ExtractedEntity,
    ExtractedRelation,
)
from app.core.graph_store import GraphEntity, GraphRelation, graph_store
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.llm_config import LLMConfig

logger = logging.getLogger(__name__)


async def build_graph_for_document(
    doc_id: str,
    kb_id: str,
    db: AsyncSession,
    llm_config: LLMConfig,
    chunk_batch_size: int = 5,
) -> dict:
    """Build knowledge graph for a single document.

    Args:
        doc_id: Document ID.
        kb_id: Knowledge base ID.
        db: Database session.
        llm_config: LLM configuration for extraction.
        chunk_batch_size: Chunks to process per LLM call.

    Returns:
        Summary dict with entity/relation counts.
    """
    if not graph_store.ready:
        return {"status": "skipped", "reason": "Neo4j not available"}

    # 1. Fetch all chunks for this document
    result = await db.execute(
        select(Chunk).where(Chunk.doc_id == doc_id).order_by(Chunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        return {"status": "skipped", "reason": "No chunks found"}

    # 2. Extract entities from chunks (batched)
    texts = [chunk.content for chunk in chunks if chunk.content and len(chunk.content.strip()) > 20]
    if not texts:
        return {"status": "skipped", "reason": "No meaningful text in chunks"}

    logger.info(f"Extracting entities from {len(texts)} chunks in document {doc_id}")
    entities, relations = await extract_entities_batch(texts, llm_config, chunk_batch_size)
    logger.info(f"Extracted {len(entities)} entities, {len(relations)} relations")

    if not entities:
        return {"status": "done", "entities": 0, "relations": 0}

    # 3. Convert to GraphEntity/GraphRelation and insert into Neo4j
    graph_entities = [
        GraphEntity(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            aliases=e.aliases,
            properties={**e.properties, "kb_id": kb_id},
        )
        for e in entities
    ]
    graph_relations = [
        GraphRelation(
            source_id=r.source_id,
            target_id=r.target_id,
            relation=r.relation,
            weight=r.weight,
        )
        for r in relations
    ]

    graph_store.create_entities(kb_id, graph_entities)
    graph_store.create_relations(graph_relations)

    # 4. Link chunks to entities (:MENTIONS)
    _link_chunks_to_entities(kb_id, chunks, entities)

    # 5. Embed graph nodes/edges into vector store
    graph_vector_result = {"nodes_embedded": 0, "edges_embedded": 0}
    try:
        from app.core.graph_to_vector import embed_graph_to_vector
        # Get all nodes for this KB from Neo4j (including newly created ones)
        all_nodes = graph_store.get_all_entities(kb_id)
        # Get all edges for this KB
        sub = graph_store.get_full_graph(kb_id, limit=5000)
        graph_vector_result = await embed_graph_to_vector(
            kb_id=kb_id,
            nodes=all_nodes if all_nodes else sub.nodes,
            edges=sub.edges if sub.edges else [],
            embedding_model=None,  # use default
        )
    except Exception as e:
        logger.warning(f"Graph-to-vector embedding skipped: {e}")

    return {
        "status": "done",
        "entities": len(graph_entities),
        "relations": len(graph_relations),
        "chunks_processed": len(texts),
        "vectors_embedded": graph_vector_result,
    }


async def build_graph_for_kb(
    kb_id: str,
    db: AsyncSession,
    llm_config: LLMConfig,
) -> dict:
    """Build knowledge graph for an entire knowledge base.

    Processes all documents that have been chunked but not yet graphed.
    """
    if not graph_store.ready:
        return {"status": "skipped", "reason": "Neo4j not available"}

    # Find documents with status "done" (already chunked)
    result = await db.execute(
        select(Document).where(
            Document.kb_id == kb_id,
            Document.parse_status == "done",
        )
    )
    docs = result.scalars().all()

    total_entities = 0
    total_relations = 0
    results = []

    for doc in docs:
        doc_result = await build_graph_for_document(
            doc_id=doc.id,
            kb_id=kb_id,
            db=db,
            llm_config=llm_config,
        )
        results.append({"doc_id": doc.id, "filename": doc.filename, **doc_result})
        total_entities += doc_result.get("entities", 0)
        total_relations += doc_result.get("relations", 0)

    # Final pass: embed ALL graph entities/edges into vector store (force to catch missed ones)
    vector_result = {"nodes_embedded": 0, "edges_embedded": 0}
    try:
        from app.core.graph_to_vector import embed_graph_to_vector
        all_nodes = graph_store.get_all_entities(kb_id)
        sub = graph_store.get_full_graph(kb_id, limit=5000)
        vector_result = await embed_graph_to_vector(
            kb_id=kb_id,
            nodes=all_nodes if all_nodes else sub.nodes,
            edges=sub.edges if sub.edges else [],
            embedding_model=None,
        )
    except Exception as e:
        logger.warning(f"Graph vector embedding failed: {e}")

    return {
        "status": "done",
        "documents_processed": len(docs),
        "total_entities": total_entities,
        "total_relations": total_relations,
        "vectors_embedded": vector_result,
        "details": results,
    }


async def delete_graph_for_document(doc_id: str, kb_id: str, db: AsyncSession):
    """Remove graph data for a document (entities that are only from this doc)."""
    if not graph_store.ready:
        return

    # Get chunks for this document
    result = await db.execute(
        select(Chunk).where(Chunk.doc_id == doc_id)
    )
    chunks = result.scalars().all()
    chunk_ids = [c.id for c in chunks]

    # Remove :MENTIONS relations to these chunks
    if chunk_ids:
        from app.core.graph_store import _get_driver
        from app.config import settings as app_settings
        driver = _get_driver()
        if driver:
            with driver.session(database=app_settings.NEO4J_DATABASE) as session:
                session.run(
                    """
                    MATCH (:Entity)-[r:MENTIONS]->(:Chunk)
                    WHERE r.chunk_id IN $chunk_ids
                    DELETE r
                    """,
                    chunk_ids=chunk_ids,
                )

    logger.info(f"Removed graph links for document {doc_id}")


def _link_chunks_to_entities(kb_id: str, chunks: list[Chunk], entities: list[ExtractedEntity]):
    """Create :MENTIONS edges from entities to chunks where the entity name appears."""
    from app.core.graph_store import _get_driver
    from app.config import settings as app_settings

    driver = _get_driver()
    if not driver:
        return

    entity_names = {e.name.lower(): e.id for e in entities}

    with driver.session(database=app_settings.NEO4J_DATABASE) as session:
        for chunk in chunks:
            content_lower = (chunk.content or "").lower()
            for name_lower, entity_id in entity_names.items():
                if name_lower in content_lower:
                    session.run(
                        """
                        MATCH (n:Entity {id: $entity_id})
                        CREATE (n)-[:MENTIONS {chunk_id: $chunk_id, doc_id: $doc_id}]->(c:Chunk)
                        """,  # Note: Chunk node may not exist yet — this is OK, Neo4j creates it
                        entity_id=entity_id,
                        chunk_id=chunk.id,
                        doc_id=chunk.doc_id,
                    )
