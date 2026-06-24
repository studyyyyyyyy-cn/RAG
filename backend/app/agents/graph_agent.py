"""Knowledge graph agent — generates ECharts graph visualization specs.

Follows the same pattern as ChartAgent but for graph-type output.
"""

import json

from app.agents.base_agent import BaseAgent
from app.core.llm_manager import chat_completion
from app.core.graph_store import graph_store
from app.core.graph_retriever import retrieve_graph_context
from app.models.llm_config import LLMConfig


GRAPH_PROMPT = """基于以下资料和知识图谱数据，为用户的问题生成一个 ECharts graph 类型的可视化配置。

要求：
1. 返回合法的 JSON 格式 ECharts option，类型为 graph（力导向图）
2. 包含 nodes 数组：每个节点有 id, name, category（数字索引）, symbolSize
3. 包含 links 数组：每条边有 source（节点id）, target（节点id）, label（关系标签）
4. 包含 categories 数组：每个分类有 name 字段，用不同颜色
5. 使用 force 布局（repulsion: 300, edgeLength: [100, 300]）
6. 数据从参考资料中提取，不要编造
7. 使用中文标签

参考资料：
{context}

知识图谱数据：
{graph_data}

用户问题：{query}

请仅返回 ECharts graph option 的 JSON 对象，用 ```json ``` 包裹。"""


GRAPH_TEMPLATE_OPTION = {
    "tooltip": {
        "formatter": "{b} ({c})",
    },
    "legend": [{"data": []}],
    "series": [{
        "type": "graph",
        "layout": "force",
        "symbolSize": 40,
        "roam": True,
        "draggable": True,
        "force": {
            "repulsion": 300,
            "edgeLength": [100, 300],
            "gravity": 0.1,
        },
        "emphasis": {
            "focus": "adjacency",
            "lineStyle": {"width": 5},
        },
        "categories": [],
        "nodes": [],
        "links": [],
        "lineStyle": {
            "color": "source",
            "curveness": 0.2,
            "width": 1.5,
        },
        "label": {
            "show": True,
            "position": "right",
            "fontSize": 12,
        },
    }],
}


class GraphAgent(BaseAgent):
    agent_type = "knowledge_graph"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        """Generate an ECharts graph visualization from knowledge base data.

        Combines:
        - Retrieved context (vector search results)
        - Neo4j graph data (if available)
        """
        context_text = "\n\n".join(
            f"[{c.get('source', '未知')}] {c.get('content', '')[:500]}" for c in context[:10]
        )

        # Try to get Neo4j graph data
        graph_json = {"nodes": [], "links": [], "categories": []}
        try:
            # Try to get kb_id from context metadata
            kb_id = None
            for c in context:
                if c.get("kb_id"):
                    kb_id = c["kb_id"]
                    break

            if kb_id and graph_store.ready:
                subgraph = graph_store.get_full_graph(kb_id, limit=100)
                if subgraph.nodes:
                    # Map entity types to category indices
                    type_set = sorted(set(n.get("entity_type", "CONCEPT") for n in subgraph.nodes))
                    type_to_idx = {t: i for i, t in enumerate(type_set)}

                    graph_json["categories"] = [{"name": t} for t in type_set]
                    graph_json["nodes"] = [
                        {
                            "id": n["id"],
                            "name": n["name"],
                            "category": type_to_idx.get(n.get("entity_type", "CONCEPT"), 0),
                            "symbolSize": max(20, min(60, 20 + len(n.get("name", "")) * 2)),
                        }
                        for n in subgraph.nodes
                    ]
                    graph_json["links"] = [
                        {
                            "source": e["source"],
                            "target": e["target"],
                            "label": e.get("relation", ""),
                        }
                        for e in subgraph.edges
                    ]
        except Exception as e:
            pass  # Graph data is optional

        messages = [
            {"role": "user", "content": GRAPH_PROMPT.format(
                context=context_text,
                graph_data=json.dumps(graph_json, ensure_ascii=False, indent=2),
                query=query,
            )}
        ]

        result = await chat_completion(messages, llm_config, stream=False)

        # Extract JSON from response
        chart_spec = self._extract_json(result)

        return {
            "type": "knowledge_graph",
            "content": {
                "text": f"根据知识库数据生成了知识图谱可视化：",
                "graph_spec": chart_spec,
                "citations": [{"source": c.get("source", "未知")} for c in context],
            },
        }

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response."""
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass
        elif "```" in text:
            try:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "tooltip": {},
                "series": [{"type": "graph", "data": [], "links": []}],
            }


graph_agent = GraphAgent()
