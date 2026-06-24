"""Entity and relation extraction using LLM for knowledge graph construction.

Extracts typed entities (PERSON, ORGANIZATION, CONCEPT, etc.) and their
relationships from text chunks. Uses the existing LLM pipeline.
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ENTITY_TYPES = [
    "PERSON",        # 人物
    "ORGANIZATION",  # 组织/公司
    "PRODUCT",       # 产品/商品
    "CONCEPT",       # 概念/术语
    "LOCATION",      # 地点
    "TIME",          # 时间
    "EVENT",         # 事件
    "ATTRIBUTE",     # 属性/数值
]


@dataclass
class ExtractedEntity:
    """An entity extracted from text."""
    id: str           # unique ID (e.g., md5 hash of normalized name)
    name: str         # display name
    entity_type: str  # one of ENTITY_TYPES
    aliases: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class ExtractedRelation:
    """A relation between two extracted entities."""
    source_id: str
    target_id: str
    relation: str    # e.g., "生产", "属于", "位于", "成立于"
    weight: float = 1.0


# ── Extraction prompt ────────────────────────────────────────────────────

EXTRACTION_SYSTEM = """你是一个知识图谱实体关系抽取专家。从给定文本中提取所有重要实体及其关系。

实体类型包括：PERSON(人物), ORGANIZATION(组织/公司), PRODUCT(产品/商品), CONCEPT(概念/术语), LOCATION(地点), TIME(时间), EVENT(事件), ATTRIBUTE(属性/数值)

要求：
1. 每个实体提取 name（名称）、type（类型）、aliases（别名列表）
2. 实体间的关系提取 source（源实体名）、target（目标实体名）、relation（关系描述）
3. 只提取文本中明确出现的信息，不要编造
4. 返回严格JSON格式

输出格式：
```json
{
  "entities": [
    {"name": "实体名", "type": "实体类型", "aliases": ["别名1"]}
  ],
  "relations": [
    {"source": "源实体名", "target": "目标实体名", "relation": "关系描述"}
  ]
}
```"""


async def extract_entities_from_text(text: str, llm_config) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
    """Extract entities and relations from a single text chunk using LLM.

    Args:
        text: The text to analyze.
        llm_config: LLMConfig for the LLM call.

    Returns:
        Tuple of (entities, relations).
    """
    from app.core.llm_manager import chat_completion

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM},
        {"role": "user", "content": f"请从以下文本中提取实体和关系：\n\n{text[:3000]}"},
    ]

    try:
        result = await chat_completion(messages, llm_config, stream=False)
        data = _parse_json_response(result)
        entities, relations = _normalize_extraction(data, text)
        logger.debug(f"Extracted {len(entities)} entities, {len(relations)} relations")
        return entities, relations
    except Exception as e:
        logger.warning(f"Entity extraction failed: {e}")
        return [], []


async def extract_entities_batch(
    texts: list[str],
    llm_config,
    batch_size: int = 5,
) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
    """Extract entities from multiple text chunks with batching.

    Merges results with entity deduplication across chunks.
    """
    all_entities: dict[str, ExtractedEntity] = {}  # id -> entity
    all_relations: list[ExtractedRelation] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        combined_text = "\n\n---\n\n".join(batch)
        entities, relations = await extract_entities_from_text(combined_text, llm_config)

        # Merge entities with dedup
        for entity in entities:
            eid = entity.id
            if eid in all_entities:
                # Merge aliases
                existing = all_entities[eid]
                for alias in entity.aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)
                # Merge properties
                existing.properties.update(entity.properties)
            else:
                all_entities[eid] = entity

        all_relations.extend(relations)

    return list(all_entities.values()), all_relations


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response."""
    # Try ```json block
    json_match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        obj_match = re.search(r'\{.*\}', text, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                pass
    return {"entities": [], "relations": []}


def _normalize_extraction(
    data: dict,
    source_text: str,
) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
    """Normalize raw LLM output into typed dataclasses."""
    import hashlib

    raw_entities = data.get("entities", [])
    raw_relations = data.get("relations", [])

    # Build entity map: name -> ExtractedEntity
    entity_map: dict[str, ExtractedEntity] = {}
    for item in raw_entities:
        name = str(item.get("name", "")).strip()
        if not name or len(name) < 2:
            continue
        entity_type = str(item.get("type", "CONCEPT")).strip().upper()
        if entity_type not in ENTITY_TYPES:
            entity_type = "CONCEPT"
        aliases = [str(a).strip() for a in item.get("aliases", []) if str(a).strip()]
        props = item.get("properties", {}) or {}

        eid = _make_entity_id(name, entity_type)
        entity_map[name] = ExtractedEntity(
            id=eid,
            name=name,
            entity_type=entity_type,
            aliases=aliases,
            properties=props,
        )

    # Normalize relations
    relations: list[ExtractedRelation] = []
    seen_relations = set()
    for item in raw_relations:
        source_name = str(item.get("source", "")).strip()
        target_name = str(item.get("target", "")).strip()
        relation = str(item.get("relation", "相关")).strip()
        if not source_name or not target_name:
            continue

        source_entity = entity_map.get(source_name)
        target_entity = entity_map.get(target_name)
        if not source_entity or not target_entity:
            continue

        rel_key = (source_entity.id, target_entity.id, relation)
        if rel_key not in seen_relations:
            seen_relations.add(rel_key)
            relations.append(ExtractedRelation(
                source_id=source_entity.id,
                target_id=target_entity.id,
                relation=relation,
                weight=1.0,
            ))

    return list(entity_map.values()), relations


def _make_entity_id(name: str, entity_type: str) -> str:
    """Generate a stable entity ID from name + type."""
    import hashlib
    raw = f"{entity_type}:{name}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]
