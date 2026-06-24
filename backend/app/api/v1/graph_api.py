"""Knowledge Graph API — standalone endpoints for graph data and visualization."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.knowledge_base import KnowledgeBase
from app.core.graph_store import graph_store

router = APIRouter()


@router.get("/kb/{kb_id}/graph")
async def get_kb_graph(
    kb_id: str,
    limit: int = Query(200, ge=10, le=1000),
    entity_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get the full knowledge graph for a knowledge base.

    Returns nodes, links, and categories for ECharts force-directed graph.
    """
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if not graph_store.ready:
        return {
            "status": "unavailable",
            "message": "Neo4j is not connected. Start Neo4j and restart the backend.",
            "nodes": [],
            "links": [],
            "categories": [],
        }

    subgraph = graph_store.get_full_graph(kb_id, limit=limit)

    # Build categories from entity types
    type_set = sorted(set(n.get("entity_type", "CONCEPT") for n in subgraph.nodes))
    categories = [{"name": t} for t in type_set]
    type_to_idx = {t: i for i, t in enumerate(type_set)}

    # Apply optional type filter
    if entity_type:
        subgraph.nodes = [n for n in subgraph.nodes if n.get("entity_type") == entity_type]

    nodes = [
        {
            "id": n["id"],
            "name": n["name"],
            "category": type_to_idx.get(n.get("entity_type", "CONCEPT"), 0),
            "entity_type": n.get("entity_type", ""),
            "symbolSize": max(20, min(60, 20 + len(n.get("name", "")) * 2)),
        }
        for n in subgraph.nodes
    ]

    node_ids = {n["id"] for n in nodes}
    links = [
        {
            "source": e["source"],
            "target": e["target"],
            "label": e.get("relation", ""),
            "weight": e.get("weight", 1.0),
        }
        for e in subgraph.edges
        if e["source"] in node_ids and e["target"] in node_ids
    ]

    return {
        "status": "ok",
        "total_nodes": len(nodes),
        "total_edges": len(links),
        "categories": categories,
        "nodes": nodes,
        "links": links,
    }


@router.get("/kb/{kb_id}/graph/types")
async def get_entity_types(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get distinct entity types in a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if not graph_store.ready:
        return {"types": [], "count": 0}

    types = graph_store.get_entity_types(kb_id)
    count = graph_store.get_entity_count(kb_id)

    return {
        "types": types,
        "total_entities": count,
    }


@router.get("/kb/{kb_id}/graph/entity/{entity_id}")
async def get_entity_neighbors(
    kb_id: str,
    entity_id: str,
    hops: int = Query(1, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
):
    """Get an entity and its N-hop neighbors."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if not graph_store.ready:
        raise HTTPException(status_code=503, detail="Graph database unavailable")

    subgraph = graph_store.get_neighbors(entity_id, hops=hops)

    return {
        "center": subgraph.center_entity,
        "nodes": subgraph.nodes,
        "edges": subgraph.edges,
        "total_relations": len(subgraph.edges),
    }
