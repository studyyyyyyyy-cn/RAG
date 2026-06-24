"""Report generation agent — produces structured HTML reports."""

from app.agents.base_agent import BaseAgent
from app.core.llm_manager import chat_completion
from app.models.llm_config import LLMConfig


REPORT_PROMPT = """基于以下参考资料，为用户的问题生成一份结构化的 HTML 报表。

要求：
1. 使用语义化 HTML（h2/h3 标题、table、ul/ol 列表、p 段落）
2. 内联 CSS 样式（专业简洁的风格，浅色主题）
3. 表格table使用斑马纹样式，边框清晰
4. 重要：表格的表头和数据单元格文字颜色必须使用深色文字（如 #333333、#1a1a1a 等），禁止文字颜色为白色或浅色，确保在浅色背景下清晰可读
5. 包含报表标题、摘要、数据区域、结论，报表标题居中
6. 数据从参考资料中提取，标注来源
7. 不要编造数据

参考资料：
{context}

用户问题：{query}

请返回完整的 HTML 片段（从 <div> 开始，不需要 <html>/<body>）。"""


class ReportAgent(BaseAgent):
    agent_type = "report"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        context_text = "\n\n".join(
            f"[{c.get('source', '未知')}] {c.get('content', '')}" for c in context
        )

        messages = [
            {"role": "user", "content": REPORT_PROMPT.format(context=context_text, query=query)}
        ]

        html_content = await chat_completion(messages, llm_config, stream=False)

        # Clean up if wrapped in code block
        if "```html" in html_content:
            try:
                start = html_content.index("```html") + 7
                end = html_content.index("```", start)
                html_content = html_content[start:end].strip()
            except ValueError:
                pass  # Keep original content if parsing fails

        return {
            "type": "report",
            "content": {
                "text": "根据知识库数据为您生成了以下报表：",
                "html_content": html_content,
                "citations": [{"source": c.get("source", "")} for c in context],
            },
        }


report_agent = ReportAgent()
