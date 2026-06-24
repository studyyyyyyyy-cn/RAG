"""Graph-based retrieval: entity linking → traversal → fusion with vectors.

On query → finds matching entities in Neo4j → traverses neighbors →
extracts subgraph context → merges with dense retrieval results via RRF.
"""

import logging
from dataclasses import dataclass, field

from app.core.graph_store import graph_store, SubGraph
from app.core.retriever import RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class GraphContext:
    """Graph retrieval result."""
    subgraph: SubGraph
    entity_names: list[str]
    relation_texts: list[str]
    summary: str  # Natural-language summary of the subgraph


async def retrieve_graph_context(
    query: str,
    kb_id: str,
    top_k_entities: int = 5,
    hops: int = 1,
) -> GraphContext:
    """Search the knowledge graph for entities and relations relevant to query.

    Steps:
    1. Search entities by name matching query
    2. For top matching entities, traverse N-hop neighbors
    3. Build a natural-language summary of found relations

    Args:
        query: User query.
        kb_id: Knowledge base ID.
        top_k_entities: Max entities to start traversal from.
        hops: Traversal depth (1 = direct neighbors, 2 = neighbors-of-neighbors).

    Returns:
        GraphContext with subgraph and text summary.
    """
    if not graph_store.ready:
        return GraphContext(
            subgraph=SubGraph(nodes=[], edges=[]),
            entity_names=[],
            relation_texts=[],
            summary="",
        )

    # 1. Find matching entities
    matching_entities = graph_store.search_entities(kb_id, query, top_k=top_k_entities)
    if not matching_entities:
        # Try single keywords
        for word in query.split():
            if len(word) >= 2:
                matching_entities = graph_store.search_entities(kb_id, word, top_k=3)
                if matching_entities:
                    break

    if not matching_entities:
        return GraphContext(
            subgraph=SubGraph(nodes=[], edges=[]),
            entity_names=[],
            relation_texts=[],
            summary="",
        )

    # 2. Traverse from each matching entity
    all_nodes: dict[str, dict] = {}
    all_edges: dict[tuple, dict] = {}
    entity_names: list[str] = []

    for entity in matching_entities:
        entity_names.append(entity.get("name", ""))
        sub = graph_store.get_neighbors(entity["id"], hops=hops)
        for node in sub.nodes:
            all_nodes[node["id"]] = node
        for edge in sub.edges:
            edge_key = (edge["source"], edge["target"], edge.get("relation", ""))
            if edge_key not in all_edges:
                all_edges[edge_key] = edge

    # 3. Build relation texts
    relation_texts = []
    for (src, tgt, rel), edge in all_edges.items():
        src_name = all_nodes.get(src, {}).get("name", src)
        tgt_name = all_nodes.get(tgt, {}).get("name", tgt)
        relation_texts.append(f"{src_name} --[{rel}]--> {tgt_name}")

    # 4. Build summary
    summary = _build_graph_summary(query, entity_names, relation_texts)

    subgraph = SubGraph(
        nodes=list(all_nodes.values()),
        edges=list(all_edges.values()),
        center_entity=entity_names[0] if entity_names else None,
    )

    logger.info(
        f"Graph retrieval: {len(matching_entities)} seeds → "
        f"{len(all_nodes)} nodes, {len(all_edges)} edges"
    )

    return GraphContext(
        subgraph=subgraph,
        entity_names=entity_names,
        relation_texts=relation_texts,
        summary=summary,
    )


def merge_graph_with_retrieval(
    graph_context: GraphContext,
    retrieval_results: list[RetrievalResult],
    graph_weight: float = 0.3,
) -> str:
    """Merge graph context with vector retrieval results into a single prompt context.

    Args:
        graph_context: Result from retrieve_graph_context.
        retrieval_results: Results from dense retrieval pipeline.
        graph_weight: Weight of graph context vs vector context (0-1).

    Returns:
        Combined context text for the LLM prompt.
    """
    parts = []

    # Graph section
    if graph_context.summary:
        parts.append(f"【知识图谱上下文】\n{graph_context.summary}")
        if graph_context.relation_texts:
            relations_str = "\n".join(f"- {r}" for r in graph_context.relation_texts[:20])
            parts.append(f"实体关系:\n{relations_str}")

    # Vector retrieval section
    if retrieval_results:
        parts.append("\n【文档检索上下文】")
        for i, r in enumerate(retrieval_results[:5], 1):
            source = r.metadata.get("source", "未知")
            parts.append(f"[资料{i}] {source}\n{r.content[:500]}")

    return "\n\n".join(parts)


def _build_graph_summary(query: str, entity_names: list[str], relation_texts: list[str]) -> str:
    """Build a natural-language summary of graph findings."""
    if not entity_names:
        return ""

    lines = [f"与查询「{query}」相关的知识图谱实体: {', '.join(entity_names[:10])}"]
    if relation_texts:
        lines.append(f"共找到 {len(relation_texts)} 条关联关系")
    return "\n".join(lines)
