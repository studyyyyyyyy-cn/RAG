"""Chart generation agent — produces ECharts JSON specifications."""

import json

from app.agents.base_agent import BaseAgent
from app.core.llm_manager import chat_completion
from app.models.llm_config import LLMConfig


CHART_PROMPT = """基于以下参考资料，为用户的问题生成一个 ECharts 图表配置。

要求：
1. 返回合法的 JSON 格式的 ECharts option 对象
2. 选择最合适的图表类型（bar/line/pie/scatter/radar）
3. 包含 title, tooltip, legend, xAxis/yAxis (如需要), series
4. 数据从参考资料中提取，不要编造
5. 使用中文标签

参考资料：
{context}

用户问题：{query}

请仅返回 ECharts option 的 JSON 对象，不要其他文字。用 ```json ``` 包裹。"""


class ChartAgent(BaseAgent):
    agent_type = "chart"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        context_text = "\n\n".join(
            f"[{c.get('source', '未知')}] {c.get('content', '')}" for c in context
        )

        messages = [
            {"role": "user", "content": CHART_PROMPT.format(context=context_text, query=query)}
        ]

        result = await chat_completion(messages, llm_config, stream=False)

        # Extract JSON from response
        chart_spec = self._extract_json(result)

        return {
            "type": "chart",
            "content": {
                "text": f"根据知识库数据为您生成了以下图表：",
                "chart_spec": chart_spec,
                "citations": [{"source": c.get("source", "")} for c in context],
            },
        }

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON block
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
            return {"title": {"text": "数据解析失败"}, "series": []}


chart_agent = ChartAgent()
