"""Document chunking strategies.

Supports both the original RAG-Pro chunkers and the RAG-Chunking style
document-management chunkers.
"""
from dataclasses import dataclass, field
from typing import Literal
import re

from app.core.document_parser import DocumentPage


ChunkMethod = Literal[
    "naive",
    "general",
    "book",
    "paper",
    "resume",
    "table",
    "qa",
    "intelligent",
    "parent_child",
    "recursive",
]


@dataclass
class TextChunk:
    """A text chunk ready for embedding."""
    text: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    token_count: int = 0
    parent_chunk_index: int | None = None
    metadata: dict = field(default_factory=dict)


class RecursiveChunker:
    """Split text recursively by separators with overlap."""

    SEPARATORS = ["\n\n", "\n", ". ", "；", "。", " ", ""]

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~1.5 chars per token for Chinese, ~4 chars for English."""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def _split_by_separator(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text by the first applicable separator."""
        if not text.strip():
            return []

        if self._estimate_tokens(text) <= self.chunk_size:
            return [text]

        if not separators:
            # Last resort: hard split by character count
            approx_chars = self.chunk_size * 3  # rough chars-per-chunk
            return [text[i:i + approx_chars] for i in range(0, len(text), approx_chars)]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            approx_chars = self.chunk_size * 3
            parts = [text[i:i + approx_chars] for i in range(0, len(text), approx_chars)]
        else:
            parts = text.split(separator)

        result_chunks = []
        current_parts: list[str] = []
        current_tokens = 0

        for part in parts:
            part_tokens = self._estimate_tokens(part)

            if part_tokens > self.chunk_size:
                # This part itself is too large — recurse with next separator
                if current_parts:
                    result_chunks.append(separator.join(current_parts))
                    current_parts = []
                    current_tokens = 0
                sub_chunks = self._split_by_separator(part, remaining_separators)
                result_chunks.extend(sub_chunks)
            elif current_tokens + part_tokens > self.chunk_size:
                # Current accumulation is full
                result_chunks.append(separator.join(current_parts))
                current_parts = [part]
                current_tokens = part_tokens
            else:
                current_parts.append(part)
                current_tokens += part_tokens

        if current_parts:
            result_chunks.append(separator.join(current_parts))

        return result_chunks

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlapping text between adjacent chunks."""
        if len(chunks) <= 1:
            return chunks

        overlap_chars = self.chunk_overlap * 3  # rough chars estimate
        result = []

        for i, chunk in enumerate(chunks):
            if i > 0 and overlap_chars > 0:
                # Prepend tail of previous chunk
                prev_tail = chunks[i - 1][-overlap_chars:]
                chunk = prev_tail + " " + chunk
            result.append(chunk.strip())

        return result

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        """Split document pages into overlapping chunks."""
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            raw_chunks = self._split_by_separator(page.text, self.SEPARATORS)
            overlapped_chunks = self._add_overlap(raw_chunks)

            for text in overlapped_chunks:
                text = text.strip()
                if not text:
                    continue
                all_chunks.append(TextChunk(
                    text=text,
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=page.section_title,
                    token_count=self._estimate_tokens(text),
                    metadata=page.metadata,
                ))
                chunk_index += 1

        return all_chunks


class ParentChildChunker:
    """Two-level chunking: small child chunks for retrieval, large parent chunks for context.

    Child chunks (512 tokens) → used for embedding and retrieval
    Parent chunks (1536 tokens) → retrieved as context when a child chunk matches
    """

    def __init__(
        self,
        child_chunk_size: int = 512,
        child_overlap: int = 64,
        parent_chunk_size: int = 1536,
    ):
        self.child_chunker = RecursiveChunker(child_chunk_size, child_overlap)
        self.parent_chunker = RecursiveChunker(parent_chunk_size, 0)

    def chunk_pages(self, pages: list[DocumentPage]) -> tuple[list[TextChunk], list[TextChunk]]:
        """Return (child_chunks, parent_chunks) with parent references."""
        parent_chunks = self.parent_chunker.chunk_pages(pages)
        child_chunks: list[TextChunk] = []
        child_index = 0

        for parent in parent_chunks:
            # Create a temporary page from the parent chunk
            temp_page = DocumentPage(
                text=parent.text,
                page_number=parent.page_number,
                section_title=parent.section_title,
                metadata=parent.metadata,
            )
            children = self.child_chunker.chunk_pages([temp_page])

            for child in children:
                child.chunk_index = child_index
                child.parent_chunk_index = parent.chunk_index
                child_chunks.append(child)
                child_index += 1

        return child_chunks, parent_chunks


class IntelligentChunker:
    """Intelligent chunking based on document structure (headings, paragraphs, lists)."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64, min_chunk_size: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size  # Minimum tokens per chunk
        self.recursive_chunker = RecursiveChunker(chunk_size, chunk_overlap)

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        """Split based on document structure."""
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            # Detect structure: headings, paragraphs, lists
            sections = self._detect_sections(page.text)

            # Merge small sections
            merged_sections = self._merge_small_sections(sections)

            for section in merged_sections:
                # If section is too large, use recursive chunking
                if self._estimate_tokens(section["text"]) > self.chunk_size:
                    temp_page = DocumentPage(
                        text=section["text"],
                        page_number=page.page_number,
                        section_title=section.get("title") or page.section_title,
                        metadata=page.metadata,
                    )
                    sub_chunks = self.recursive_chunker.chunk_pages([temp_page])
                    for chunk in sub_chunks:
                        chunk.chunk_index = chunk_index
                        all_chunks.append(chunk)
                        chunk_index += 1
                else:
                    # Keep section intact
                    all_chunks.append(TextChunk(
                        text=section["text"].strip(),
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=section.get("title") or page.section_title,
                        token_count=self._estimate_tokens(section["text"]),
                        metadata=page.metadata,
                    ))
                    chunk_index += 1

        return all_chunks

    def _merge_small_sections(self, sections: list[dict]) -> list[dict]:
        """Merge sections that are too small."""
        if not sections:
            return sections

        merged = []
        i = 0

        while i < len(sections):
            current_section = sections[i].copy()
            current_tokens = self._estimate_tokens(current_section["text"])

            # Keep merging with next sections until we reach min_chunk_size
            while current_tokens < self.min_chunk_size and i + 1 < len(sections):
                i += 1
                next_section = sections[i]
                current_section["text"] += "\n\n" + next_section["text"]
                current_tokens = self._estimate_tokens(current_section["text"])

                # Update title: keep first non-None title
                if not current_section.get("title") and next_section.get("title"):
                    current_section["title"] = next_section["title"]

            merged.append(current_section)
            i += 1

        return merged

    def _detect_sections(self, text: str) -> list[dict]:
        """Detect document sections (headings, paragraphs)."""
        sections = []

        # Pattern for headings (Markdown style or numbered)
        heading_pattern = r'^(#{1,6}\s+.+|第[一二三四五六七八九十\d]+[章节部分].+|[一二三四五六七八九十\d]+[、\.]\s*.+)$'

        lines = text.split('\n')
        current_section = {"title": None, "text": ""}

        for line in lines:
            if re.match(heading_pattern, line.strip()):
                # Save previous section
                if current_section["text"].strip():
                    sections.append(current_section)

                # Start new section
                current_section = {"title": line.strip(), "text": line + "\n"}
            else:
                current_section["text"] += line + "\n"

        # Add last section
        if current_section["text"].strip():
            sections.append(current_section)

        return sections if sections else [{"title": None, "text": text}]

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class QAChunker:
    """Chunking optimized for Q&A documents."""

    def __init__(self):
        pass

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        """Split by Q&A pairs."""
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            qa_pairs = self._extract_qa_pairs(page.text)

            for qa in qa_pairs:
                all_chunks.append(TextChunk(
                    text=qa["text"],
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=qa.get("question", "")[:50],
                    token_count=self._estimate_tokens(qa["text"]),
                    metadata={**page.metadata, "type": "qa"},
                ))
                chunk_index += 1

        return all_chunks

    def _extract_qa_pairs(self, text: str) -> list[dict]:
        """Extract Q&A pairs from text."""
        qa_pairs = []

        # Pattern 1: Q: ... A: ... or 问: ... 答: ...
        # Use line-by-line approach to avoid catastrophic backtracking
        qa_pattern = r'(?:Q|问|Question)[:：\s]+(.+?)(?:A|答|Answer)[:：\s]+(.+?)(?=(?:Q|问|Question)[:：]|$)'
        # Limit text length per search to prevent backtracking on huge docs
        search_text = text[:100000]  # max 100k chars for Q&A extraction
        matches = re.finditer(qa_pattern, search_text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            question = match.group(1).strip()[:500]
            answer = match.group(2).strip()[:2000]
            qa_pairs.append({
                "question": question,
                "answer": answer,
                "text": f"Q: {question}\nA: {answer}"
            })

        # Pattern 2: CSV-style key-value pairs (each line is a pair)
        if not qa_pairs:
            lines = text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Try to split by common separators
                # Format: "key : value ; key : value" or "key: value"
                if ';' in line:
                    # Multiple pairs in one line
                    pairs = line.split(';')
                    for pair in pairs:
                        if ':' in pair or '：' in pair:
                            # Support both half-width and full-width colon
                            sep = '：' if '：' in pair else ':'
                            parts = pair.split(sep, 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                if key and value:
                                    qa_pairs.append({
                                        "question": key,
                                        "answer": value,
                                        "text": f"{key}: {value}"
                                    })
                elif ':' in line or '：' in line:
                    # Single pair per line
                    sep = '：' if '：' in line else ':'
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            qa_pairs.append({
                                "question": key,
                                "answer": value,
                                "text": f"{key}: {value}"
                            })

        # Pattern 3: Numbered questions
        if not qa_pairs:
            numbered_pattern = r'(\d+[、\.]\s*.+?)(?=\d+[、\.]|$)'
            matches = re.finditer(numbered_pattern, text, re.DOTALL)

            for match in matches:
                qa_text = match.group(1).strip()
                qa_pairs.append({
                    "question": qa_text[:100],
                    "text": qa_text
                })

        return qa_pairs if qa_pairs else [{"text": text}]

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class TableChunker:
    """Chunking optimized for table data."""

    def __init__(self, chunk_size: int = 512):
        self.chunk_size = chunk_size

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        """Split tables while preserving structure."""
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            # Check if this is CSV data (from document_parser)
            if page.metadata.get("headers"):
                # CSV data - each line is already a row, split by newline
                lines = page.text.strip().split('\n')
                headers = page.metadata.get("headers", [])

                for line in lines:
                    if not line.strip():
                        continue

                    # Add header context to each row for better retrieval
                    row_with_context = f"表格数据（列：{', '.join(headers)}）\n{line}"

                    all_chunks.append(TextChunk(
                        text=row_with_context,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=f"数据行 {chunk_index + 1}",
                        token_count=self._estimate_tokens(row_with_context),
                        metadata={**page.metadata, "type": "table_row"},
                    ))
                    chunk_index += 1
            else:
                # Try to extract Markdown tables
                tables = self._extract_tables(page.text)

                if tables:
                    # Process Markdown tables
                    for table in tables:
                        all_chunks.append(TextChunk(
                            text=table["text"],
                            chunk_index=chunk_index,
                            page_number=page.page_number,
                            section_title=f"Table {table['index']}",
                            token_count=self._estimate_tokens(table["text"]),
                            metadata={**page.metadata, "type": "table"},
                        ))
                        chunk_index += 1
                else:
                    # No tables, use regular chunking
                    all_chunks.append(TextChunk(
                        text=page.text,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=page.section_title,
                        token_count=self._estimate_tokens(page.text),
                        metadata=page.metadata,
                    ))
                    chunk_index += 1

        return all_chunks

    def _extract_tables(self, text: str) -> list[dict]:
        """Extract tables from text (Markdown format)."""
        tables = []

        # Markdown table pattern
        table_pattern = r'(\|.+\|[\r\n]+\|[-:\s|]+\|[\r\n]+(?:\|.+\|[\r\n]+)+)'
        matches = re.finditer(table_pattern, text)

        for idx, match in enumerate(matches):
            tables.append({
                "index": idx + 1,
                "text": match.group(1).strip()
            })

        return tables

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class GeneralChunker:
    """General fixed-size chunking with overlap."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        """Simple fixed-size chunking."""
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            text = page.text
            approx_chars_per_chunk = self.chunk_size * 3
            overlap_chars = self.chunk_overlap * 3

            start = 0
            while start < len(text):
                end = start + approx_chars_per_chunk
                chunk_text = text[start:end].strip()

                if chunk_text:
                    all_chunks.append(TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=page.section_title,
                        token_count=self._estimate_tokens(chunk_text),
                        metadata=page.metadata,
                    ))
                    chunk_index += 1

                start = end - overlap_chars

        return all_chunks

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


class NaiveChunker:
    """Simple fixed-width chunking using token-aware sizing."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        all_chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            text = page.text
            # Use character estimate consistent with other chunkers (~3 chars per token)
            approx_chars_per_chunk = self.chunk_size * 3
            overlap_chars = self.chunk_overlap * 3
            start = 0

            while start < len(text):
                end = start + approx_chars_per_chunk
                chunk_text = text[start:end].strip()
                if chunk_text:
                    all_chunks.append(TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=page.section_title,
                        token_count=_estimate_tokens(chunk_text),
                        metadata={**page.metadata, "method": "naive", "start": start, "end": end},
                    ))
                    chunk_index += 1

                start = end - overlap_chars if self.chunk_overlap > 0 else end

        return all_chunks


class BookChunker:
    """Chunk book-like long documents by chapter structure."""

    CHAPTER_PATTERN = re.compile(
        r"^(第[一二三四五六七八九十百千万0-9]+[章节部篇]|Chapter\s+\d+|CHAPTER\s+\d+)",
        re.IGNORECASE,
    )

    def __init__(self, max_chunk_size: int = 3000):
        self.max_chunk_size = max_chunk_size

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        return _sectional_chunk(
            pages,
            is_title=self._is_chapter_title,
            section_type="chapter",
            min_length=100,
            max_chunk_size=self.max_chunk_size,
        )

    def _is_chapter_title(self, line: str) -> bool:
        if self.CHAPTER_PATTERN.match(line):
            return True
        return len(line) < 50 and line and not line.endswith(("。", "！", "？", ".", "!", "?", "，", ","))


class PaperChunker:
    """Chunk paper-like documents by common academic sections."""

    SECTION_KEYWORDS = [
        "abstract", "摘要", "introduction", "引言", "绪论",
        "related work", "相关工作", "methodology", "方法", "方法论",
        "experiment", "实验", "result", "结果", "discussion", "讨论",
        "conclusion", "结论", "reference", "参考文献", "acknowledgment", "致谢",
    ]

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        return _keyword_section_chunk(
            pages,
            keywords=self.SECTION_KEYWORDS,
            section_type="paper_section",
            title_max_length=100,
            min_length=50,
        )


class ResumeChunker:
    """Chunk resumes by common resume sections."""

    SECTION_KEYWORDS = [
        "个人信息", "基本信息", "personal", "contact",
        "教育背景", "教育经历", "education",
        "工作经历", "工作经验", "experience", "employment",
        "项目经验", "项目经历", "project",
        "技能", "专业技能", "skill",
        "证书", "资格证书", "certificate",
        "自我评价", "summary", "objective",
    ]

    def chunk_pages(self, pages: list[DocumentPage]) -> list[TextChunk]:
        return _keyword_section_chunk(
            pages,
            keywords=self.SECTION_KEYWORDS,
            section_type="resume_section",
            title_max_length=50,
            min_length=20,
        )


def _estimate_tokens(text: str) -> int:
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def _sectional_chunk(
    pages: list[DocumentPage],
    is_title,
    section_type: str,
    min_length: int,
    max_chunk_size: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0

    for page in pages:
        lines = page.text.split("\n")
        current_title = page.section_title
        current_lines: list[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            if is_title(line):
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if len(content) > min_length:
                        chunks.append(TextChunk(
                            text=content,
                            chunk_index=chunk_index,
                            page_number=page.page_number,
                            section_title=current_title,
                            token_count=_estimate_tokens(content),
                            metadata={**page.metadata, "type": section_type, "title": current_title or "未命名章节"},
                        ))
                        chunk_index += 1
                current_title = line
                current_lines = [line]
                continue

            current_lines.append(line)

            if sum(len(item) for item in current_lines) > max_chunk_size:
                content = "\n".join(current_lines).strip()
                chunks.append(TextChunk(
                    text=content,
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=current_title,
                    token_count=_estimate_tokens(content),
                    metadata={**page.metadata, "type": section_type, "title": current_title or "未命名章节"},
                ))
                chunk_index += 1
                current_lines = []

        if current_lines:
            content = "\n".join(current_lines).strip()
            if len(content) > min_length:
                chunks.append(TextChunk(
                    text=content,
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=current_title,
                    token_count=_estimate_tokens(content),
                    metadata={**page.metadata, "type": section_type, "title": current_title or "未命名章节"},
                ))
                chunk_index += 1

    return chunks


def _keyword_section_chunk(
    pages: list[DocumentPage],
    keywords: list[str],
    section_type: str,
    title_max_length: int,
    min_length: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0

    for page in pages:
        current_title = page.section_title
        current_lines: list[str] = []

        for raw_line in page.text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            line_lower = line.lower()
            is_section = any(keyword in line_lower for keyword in keywords) and len(line) < title_max_length

            if is_section:
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if len(content) > min_length:
                        chunks.append(TextChunk(
                            text=content,
                            chunk_index=chunk_index,
                            page_number=page.page_number,
                            section_title=current_title,
                            token_count=_estimate_tokens(content),
                            metadata={**page.metadata, "type": section_type, "section": current_title or "未命名"},
                        ))
                        chunk_index += 1
                current_title = line
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            content = "\n".join(current_lines).strip()
            if len(content) > min_length:
                chunks.append(TextChunk(
                    text=content,
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=current_title,
                    token_count=_estimate_tokens(content),
                    metadata={**page.metadata, "type": section_type, "section": current_title or "未命名"},
                ))
                chunk_index += 1

    return chunks


def get_chunker(method: ChunkMethod, chunk_size: int = 512, chunk_overlap: int = 64, min_chunk_size: int = 50):
    """Factory function to get chunker by method.

    Args:
        method: Chunking method to use
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks in tokens
        min_chunk_size: Minimum chunk size in tokens (for intelligent chunking)
    """
    if method == "naive":
        return NaiveChunker(chunk_size, chunk_overlap)
    elif method == "book":
        return BookChunker(max_chunk_size=max(chunk_size * 3, 1500))
    elif method == "paper":
        return PaperChunker()
    elif method == "resume":
        return ResumeChunker()
    elif method == "intelligent":
        return IntelligentChunker(chunk_size, chunk_overlap, min_chunk_size)
    elif method == "qa":
        return QAChunker()
    elif method == "table":
        return TableChunker(chunk_size)
    elif method == "general":
        return GeneralChunker(chunk_size, chunk_overlap)
    elif method == "parent_child":
        return ParentChildChunker(chunk_size, chunk_overlap)
    elif method == "recursive":
        return RecursiveChunker(chunk_size, chunk_overlap)
    else:
        raise ValueError(f"Unknown chunk method: {method}")
