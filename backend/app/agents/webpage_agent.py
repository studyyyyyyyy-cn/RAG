"""Webpage generation agent that publishes generated HTML as a static page."""
import re

from app.agents.base_agent import BaseAgent
from app.core.llm_manager import chat_completion
from app.models.llm_config import LLMConfig
from app.utils.webpage_publisher import extract_title, publish_html_page


WEBPAGE_PROMPT = """基于以下参考资料，为用户的问题生成一个美观的网页展示片段。

要求：
1. 使用 HTML + 内联 CSS + 少量 JavaScript
2. 采用现代卡片式布局
3. 响应式设计，适配不同宽度
4. 可以包含交互元素，如折叠面板、标签切换等
5. 数据必须来自参考资料，并标注来源
6. 不要输出 Markdown 代码块，直接返回 HTML

参考资料：
{context}

用户问题：{query}

请直接返回完整 HTML 片段，可以包含 <style> 和 <script>。"""


class WebpageAgent(BaseAgent):
    agent_type = "webpage"

    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        context_text = "\n\n".join(
            f"[{c.get('source', '未知来源')}] {c.get('content', '')}" for c in context
        )

        messages = [
            {"role": "user", "content": WEBPAGE_PROMPT.format(context=context_text, query=query)}
        ]

        html_content = await chat_completion(messages, llm_config, stream=False)
        html_content = self._normalize_html_output(html_content)

        if not html_content:
            raise ValueError("Webpage agent returned empty HTML content")

        page_title = extract_title(html_content)
        _, page_url = publish_html_page(html_content, title=page_title)

        return {
            "type": "webpage",
            "content": {
                "text": f"已生成网页展示，打开链接浏览：{page_url}",
                "html_content": html_content,
                "page_url": page_url,
                "page_title": page_title,
                "citations": [{"source": c.get("source", "")} for c in context],
            },
        }

    @staticmethod
    def _normalize_html_output(html_content: str | None) -> str:
        """Normalize LLM output and safely remove markdown fences."""
        if not html_content:
            return ""

        normalized = html_content.strip()
        fenced_match = re.search(r"```(?:html)?\s*(.*?)```", normalized, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        if normalized.startswith("```"):
            normalized = re.sub(r"^```(?:html)?", "", normalized, flags=re.IGNORECASE).strip()
            normalized = re.sub(r"```$", "", normalized).strip()

        return normalized


webpage_agent = WebpageAgent()
