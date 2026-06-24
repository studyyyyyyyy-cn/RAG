"""Prompt templates for RAG answer generation."""


SYSTEM_PROMPT_RAG = """你是一个严谨的知识库问答助手。请严格遵守以下规则：

1. **仅基于【参考资料】中的内容回答问题**，不得编造、推测或补充参考资料中没有的信息
2. 每个关键论述必须标注来源，格式：[来源: 文档名-页码]
3. 如果参考资料不足以完整回答问题，明确说明："根据现有知识库资料，暂无法完整回答此问题"，并给出已找到的部分信息
4. 对不确定的推论使用"根据资料推测"等措辞
5. 回答使用结构化格式（标题、列表、表格等），提高可读性
6. 如果问题涉及数据统计、对比分析，尽量用表格或列表呈现"""


CONTEXT_TEMPLATE = """【参考资料】:
{context}

【置信度】: {confidence} ({confidence_label})

---
用户问题: {query}"""


INTENT_DETECTION_PROMPT = """分析用户的问题，判断最佳回答形式。仅返回以下类型之一：
- text: 普通文字回答
- chart: 需要图表展示（数据对比、趋势、统计）
- report: 需要生成结构化报表
- webpage: 需要生成网页展示
- data_table: 需要数据表格

用户问题: {query}

请仅返回类型名称，不要其他内容。"""


def build_rag_messages(
    query: str,
    context_chunks: list[dict],
    confidence: float,
    confidence_label: str,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    """Build the full message list for RAG generation.

    Args:
        query: User's question
        context_chunks: List of retrieved chunks with metadata
        confidence: Confidence score 0-1
        confidence_label: high/medium/low/very_low
        conversation_history: Previous messages for multi-turn context
    """
    # Format context from chunks
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        source = chunk.get("source", "未知文档")
        page = chunk.get("page_number", "")
        section = chunk.get("section_title", "")
        text = chunk.get("content", "")

        # Use parent content if available (larger context window)
        parent_text = chunk.get("parent_content")
        if parent_text:
            text = parent_text

        header = f"[资料{i}] {source}"
        if page:
            header += f" - 第{page}页"
        if section:
            header += f" - {section}"

        context_parts.append(f"{header}\n{text}")

    context = "\n\n---\n\n".join(context_parts)

    messages = [{"role": "system", "content": SYSTEM_PROMPT_RAG}]

    # Add conversation history for multi-turn
    if conversation_history:
        for msg in conversation_history[-6:]:  # Last 3 turns
            messages.append(msg)

    # Add current query with context
    user_content = CONTEXT_TEMPLATE.format(
        context=context,
        confidence=f"{confidence:.0%}",
        confidence_label=confidence_label,
        query=query,
    )
    messages.append({"role": "user", "content": user_content})

    return messages
