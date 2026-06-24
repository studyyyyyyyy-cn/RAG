"""Data analysis agent — produces tables + chart combinations."""

import json

from app.agents.base_agent import BaseAgent
from app.core.llm_manager import chat_completion
from app.models.llm_config import LLMConfig


DATA_ANALYSIS_PROMPT = """基于以下参考资料，对用户的问题进行数据分析。

要求返回一个 JSON 对象，包含：
1. "summary": 分析摘要文字
2. "data_table": {{ "headers": [...], "rows": [[...], ...] }}  — 结构化表格数据
3. "chart_spec": ECharts option 对象（可选，如果数据适合可视化）
4. "insights": 数据洞察列表 ["insight1", "insight2", ...]

所有数据从参考资料中提取，不要编造。

参考资料：
{context}

用户问题：{query}

请仅返回 JSON 对象，用 ```json ``` 包裹。"""


class DataAgent(BaseAgent):
    agent_type = "data_table"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        context_text = "\n\n".join(
            f"[{c.get('source', '未知')}] {c.get('content', '')}" for c in context
        )

        messages = [
            {"role": "user", "content": DATA_ANALYSIS_PROMPT.format(context=context_text, query=query)}
        ]

        result = await chat_completion(messages, llm_config, stream=False)

        # Extract JSON
        analysis = self._extract_json(result)

        return {
            "type": "composite",
            "content": {
                "text": analysis.get("summary", "数据分析完成"),
                "data_table": analysis.get("data_table", {"headers": [], "rows": []}),
                "chart_spec": analysis.get("chart_spec"),
                "insights": analysis.get("insights", []),
                "citations": [{"source": c.get("source", "")} for c in context],
            },
        }

    def _extract_json(self, text: str) -> dict:
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"summary": text, "data_table": {"headers": [], "rows": []}}


data_agent = DataAgent()
