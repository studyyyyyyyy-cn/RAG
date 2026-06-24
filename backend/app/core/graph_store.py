"""Neo4j graph store for knowledge graph operations.

Provides connection management, CRUD for entities and relations,
and Cypher-based graph traversal queries.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.core.exceptions import Neo4jNotConnectedError, EntityNotFoundError

logger = logging.getLogger(__name__)

# ── Lazy import to avoid hard dependency at import time ──────────────────
_neodriver = None


def _get_driver():
    """Lazy-load Neo4j driver (singleton)."""
    global _neodriver
    if _neodriver is not None:
        return _neodriver
    try:
        from neo4j import GraphDatabase
        _neodriver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        _neodriver.verify_connectivity()
        logger.info(f"Neo4j connected: {settings.NEO4J_URI}")
        return _neodriver
    except ImportError:
        logger.warning("neo4j driver not installed — graph features disabled")
        return None
    except Exception as e:
        logger.warning(f"Neo4j unavailable ({e}) — graph features disabled")
        _neodriver = None
        return None


def _reset_driver():
    """Close and reset the driver (for testing/reconnect)."""
    global _neodriver
    if _neodriver:
        try:
            _neodriver.close()
        except Exception:
            pass
    _neodriver = None


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class GraphEntity:
    """A node in the knowledge graph."""
    id: str
    name: str
    entity_type: str  # PERSON, ORGANIZATION, CONCEPT, etc.
    aliases: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class GraphRelation:
    """A relationship (edge) between two entities."""
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0


@dataclass
class SubGraph:
    """A sub-graph extracted by traversal."""
    nodes: list[dict]
    edges: list[dict]
    center_entity: Optional[str] = None


# ── Graph operations ─────────────────────────────────────────────────────

class GraphStore:
    """Neo4j-backed knowledge graph store.

    Follows the same singleton + lazy-init pattern as VectorStore.
    """

    def __init__(self):
        self._ready = False

    @property
    def ready(self) -> bool:
        """Check if Neo4j is connected and ready."""
        driver = _get_driver()
        return driver is not None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def clear_kb(self, kb_id: str):
        """Remove all nodes and relations for a knowledge base."""
        if not self.ready:
            return
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run(
                "MATCH (n {kb_id: $kb_id}) DETACH DELETE n",
                kb_id=kb_id,
            )
        logger.info(f"Cleared graph for KB {kb_id}")

    # ── Entity CRUD ────────────────────────────────────────────────────

    def create_entities(self, kb_id: str, entities: list[GraphEntity]):
        """Batch-create entity nodes."""
        if not self.ready or not entities:
            return
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            for e in entities:
                session.run(
                    """
                    MERGE (n:Entity {id: $id})
                    SET n.name = $name,
                        n.entity_type = $entity_type,
                        n.kb_id = $kb_id,
                        n.aliases = $aliases
                    SET n += $properties
                    """,
                    id=e.id,
                    name=e.name,
                    entity_type=e.entity_type,
                    kb_id=kb_id,
                    aliases=e.aliases,
                    properties=e.properties,
                )
        logger.info(f"Created/updated {len(entities)} entities for KB {kb_id}")

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Get a single entity by ID."""
        if not self.ready:
            return None
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(
                "MATCH (n:Entity {id: $id}) RETURN n",
                id=entity_id,
            )
            record = result.single()
            if record:
                node = record["n"]
                return dict(node.items())
        return None

    def search_entities(self, kb_id: str, query: str, top_k: int = 10) -> list[dict]:
        """Fuzzy search entities by name."""
        if not self.ready:
            return []
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (n:Entity {kb_id: $kb_id})
                WHERE toLower(n.name) CONTAINS toLower($query)
                RETURN n
                ORDER BY n.name
                LIMIT $top_k
                """,
                kb_id=kb_id,
                query=query,
                top_k=top_k,
            )
            return [dict(record["n"].items()) for record in result]

    def get_all_entities(self, kb_id: str, entity_type: Optional[str] = None) -> list[dict]:
        """Get all entities in a KB, optionally filtered by type."""
        if not self.ready:
            return []
        driver = _get_driver()
        if entity_type:
            result = driver.session(database=settings.NEO4J_DATABASE).run(
                "MATCH (n:Entity {kb_id: $kb_id, entity_type: $entity_type}) RETURN n ORDER BY n.name",
                kb_id=kb_id, entity_type=entity_type,
            )
        else:
            result = driver.session(database=settings.NEO4J_DATABASE).run(
                "MATCH (n:Entity {kb_id: $kb_id}) RETURN n ORDER BY n.name",
                kb_id=kb_id,
            )
        return [dict(record["n"].items()) for record in result]

    def get_entity_count(self, kb_id: str) -> int:
        """Count entities in a KB."""
        if not self.ready:
            return 0
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(
                "MATCH (n:Entity {kb_id: $kb_id}) RETURN count(n) AS cnt",
                kb_id=kb_id,
            )
            record = result.single()
            return record["cnt"] if record else 0

    # ── Relation CRUD ──────────────────────────────────────────────────

    def create_relations(self, relations: list[GraphRelation]):
        """Batch-create relationships between entities."""
        if not self.ready or not relations:
            return
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            for r in relations:
                session.run(
                    """
                    MATCH (a:Entity {id: $source_id})
                    MATCH (b:Entity {id: $target_id})
                    MERGE (a)-[rel:RELATED_TO {relation: $relation}]->(b)
                    SET rel.weight = $weight
                    """,
                    source_id=r.source_id,
                    target_id=r.target_id,
                    relation=r.relation,
                    weight=r.weight,
                )
        logger.info(f"Created/updated {len(relations)} relations")

    # ── Graph traversal ────────────────────────────────────────────────

    def get_neighbors(self, entity_id: str, hops: int = 1) -> SubGraph:
        """Get an entity and its N-hop neighbors as a sub-graph."""
        nodes = []
        edges = []
        center_name = None

        if not self.ready:
            return SubGraph(nodes=[], edges=[])

        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (center:Entity {id: $entity_id})
                OPTIONAL MATCH path = (center)-[r:RELATED_TO*1..$hops]-(neighbor:Entity)
                RETURN center, collect(DISTINCT r) AS rels, collect(DISTINCT neighbor) AS neighbors
                """,
                entity_id=entity_id,
                hops=hops,
            )
            record = result.single()
            if not record:
                return SubGraph(nodes=[], edges=[])

            center = record["center"]
            center_name = center.get("name", "")
            seen_ids = set()

            # Add center node
            nodes.append({
                "id": center.get("id"),
                "name": center.get("name"),
                "entity_type": center.get("entity_type"),
                "category": _entity_category_index(center.get("entity_type", "")),
            })
            seen_ids.add(center.get("id"))

            # Collect relations
            rel_list = record.get("rels") or []
            neighbor_list = record.get("neighbors") or []

            # Deduplicate relations (may come as nested lists from variable-length path)
            flat_rels = []
            for item in rel_list:
                if isinstance(item, list):
                    flat_rels.extend(item)
                else:
                    flat_rels.append(item)

            seen_edges = set()
            for rel in flat_rels:
                edge_key = (rel.start_node.get("id"), rel.end_node.get("id"), rel.get("relation"))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": rel.start_node.get("id"),
                        "target": rel.end_node.get("id"),
                        "relation": rel.get("relation"),
                        "weight": rel.get("weight", 1.0),
                    })

            # Add neighbor nodes
            for neighbor in neighbor_list:
                nid = neighbor.get("id")
                if nid and nid not in seen_ids:
                    seen_ids.add(nid)
                    nodes.append({
                        "id": nid,
                        "name": neighbor.get("name"),
                        "entity_type": neighbor.get("entity_type"),
                        "category": _entity_category_index(neighbor.get("entity_type", "")),
                    })

        return SubGraph(
            nodes=nodes,
            edges=edges,
            center_entity=center_name,
        )

    def get_full_graph(self, kb_id: str, limit: int = 200) -> SubGraph:
        """Get the entire knowledge graph for a KB (up to limit nodes)."""
        nodes = []
        edges = []

        if not self.ready:
            return SubGraph(nodes=[], edges=[])

        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Get nodes
            node_result = session.run(
                "MATCH (n:Entity {kb_id: $kb_id}) RETURN n ORDER BY n.name LIMIT $limit",
                kb_id=kb_id, limit=limit,
            )
            seen_ids = set()
            for record in node_result:
                node = record["n"]
                nid = node.get("id")
                seen_ids.add(nid)
                nodes.append({
                    "id": nid,
                    "name": node.get("name"),
                    "entity_type": node.get("entity_type"),
                    "category": _entity_category_index(node.get("entity_type", "")),
                })

            # Get edges between these nodes
            edge_result = session.run(
                """
                MATCH (a:Entity {kb_id: $kb_id})-[r:RELATED_TO]-(b:Entity {kb_id: $kb_id})
                WHERE a.id IN $node_ids AND b.id IN $node_ids
                RETURN a.id AS source, b.id AS target, r.relation AS relation, r.weight AS weight
                """,
                kb_id=kb_id,
                node_ids=list(seen_ids),
            )
            for record in edge_result:
                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "relation": record["relation"],
                    "weight": record.get("weight", 1.0),
                })

        logger.info(f"Retrieved full graph: {len(nodes)} nodes, {len(edges)} edges")
        return SubGraph(nodes=nodes, edges=edges)

    def get_entity_types(self, kb_id: str) -> list[str]:
        """Get distinct entity types in a KB."""
        if not self.ready:
            return []
        driver = _get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run(
                "MATCH (n:Entity {kb_id: $kb_id}) RETURN DISTINCT n.entity_type AS t ORDER BY t",
                kb_id=kb_id,
            )
            return [record["t"] for record in result]


# ── Helpers ───────────────────────────────────────────────────────────────

_ENTITY_CATEGORIES = {
    "PERSON": 0,
    "ORGANIZATION": 1,
    "PRODUCT": 2,
    "CONCEPT": 3,
    "LOCATION": 4,
    "TIME": 5,
    "EVENT": 6,
    "ATTRIBUTE": 7,
}


def _entity_category_index(entity_type: str) -> int:
    """Map entity type string to category index for ECharts coloring."""
    return _ENTITY_CATEGORIES.get(entity_type.upper(), 3)


# ── Singleton ─────────────────────────────────────────────────────────────

graph_store = GraphStore()
