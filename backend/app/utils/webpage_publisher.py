"""Helpers for publishing generated HTML pages as static files."""
import re
import uuid
from pathlib import Path

from app.config import settings


PUBLISHED_PAGES_DIR = Path(settings.UPLOAD_DIR) / "published_pages"


def ensure_published_pages_dir() -> Path:
    """Ensure the published-pages directory exists."""
    PUBLISHED_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    return PUBLISHED_PAGES_DIR


def build_full_html(html_content: str, title: str) -> str:
    """Wrap an HTML snippet into a complete standalone HTML document."""
    if "<html" in html_content.lower():
        return html_content

    safe_title = title or "Generated Webpage"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
</head>
<body>
{html_content}
</body>
</html>
"""


def publish_html_page(html_content: str, title: str | None = None) -> tuple[str, str]:
    """Persist a generated HTML page and return (page_path, page_url)."""
    output_dir = ensure_published_pages_dir()
    page_id = uuid.uuid4().hex
    filename = f"{page_id}.html"
    page_path = output_dir / filename

    page_title = title or "Generated Webpage"
    full_html = build_full_html(html_content, page_title)
    page_path.write_text(full_html, encoding="utf-8")

    return str(page_path), f"/published-pages/{filename}"


def extract_title(html_content: str) -> str:
    """Extract a human-readable title from generated HTML."""
    title_match = re.search(r"<h[1-2][^>]*>(.*?)</h[1-2]>", html_content, flags=re.IGNORECASE | re.DOTALL)
    if not title_match:
        return "Generated Webpage"

    raw_title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
    return raw_title or "Generated Webpage"
