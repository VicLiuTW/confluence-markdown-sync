"""Bidirectional HTML<->Markdown conversion with Confluence image handling."""

import re

import markdown
from markdownify import markdownify


def md_to_confluence_html(md_text: str) -> str:
    """Convert Markdown to Confluence Storage Format HTML.

    Local image refs ![alt](path) are replaced with Confluence ac:image tags.
    External https:// image URLs are left as standard <img> tags.
    """
    # Pre-process: find local image refs and replace with placeholders
    placeholders = {}
    counter = [0]

    def replace_local_image(match):
        alt = match.group(1)
        path = match.group(2)
        if re.match(r'https?://', path):
            return match.group(0)
        filename = path.split("/")[-1]
        placeholder = f"ACIMAGE{counter[0]}ACIMAGE"
        placeholders[placeholder] = filename
        counter[0] += 1
        return placeholder

    processed = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_local_image, md_text)

    # Convert MD to HTML
    html = markdown.markdown(processed, extensions=["tables", "fenced_code"])

    # Replace placeholders with ac:image tags
    for placeholder, filename in placeholders.items():
        ac_tag = f'<ac:image><ri:attachment ri:filename="{filename}"/></ac:image>'
        html = html.replace(placeholder, ac_tag)
        # Also handle markdown wrapping the placeholder in <p> tags
        html = html.replace(f"<p>{ac_tag}</p>", ac_tag)

    # Clean up <p> wrapping around ac:image tags
    html = re.sub(
        r'<p>\s*(<ac:image>[^<]*(?:<[^/][^>]*>[^<]*)*</ac:image>)\s*</p>',
        r'\1',
        html,
    )

    # Prepend Confluence TOC macro
    toc = (
        '<ac:structured-macro ac:name="toc">'
        '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
        '</ac:structured-macro>\n'
    )
    return toc + html


def confluence_html_to_md(html: str) -> str:
    """Convert Confluence HTML to Markdown.

    ac:image tags become [圖片: filename] placeholders.
    Other ac: and ri: tags are stripped (content kept).
    """
    # Replace ac:image tags with placeholder text
    def replace_ac_image(match):
        inner = match.group(1)
        filename_match = re.search(r'ri:filename="([^"]+)"', inner)
        filename = filename_match.group(1) if filename_match else "unknown"
        return f"[圖片: {filename}]"

    html = re.sub(r'<ac:image>(.*?)</ac:image>', replace_ac_image, html, flags=re.DOTALL)

    # Remove ac: and ri: tags, keep content
    html = re.sub(r'</?(?:ac|ri):[^>]*>', '', html)

    # Convert to Markdown
    result = markdownify(html, heading_style="atx", bullets="-", strip=["script", "style"])

    # Collapse 3+ newlines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


def extract_image_refs(md_text: str) -> list:
    """Find all local image refs in Markdown (excludes https?:// URLs).

    Returns list of {"filename": "name.png", "path": "../images/name.png"}.
    """
    refs = []
    for match in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', md_text):
        path = match.group(2)
        if not re.match(r'https?://', path):
            filename = path.split("/")[-1]
            refs.append({"filename": filename, "path": path})
    return refs


def strip_sync_metadata(md_text: str) -> str:
    """Remove sync metadata comment lines from the top of Markdown content.

    Removes lines starting with:
      <!-- sync from:
      <!-- confluence version:
      <!-- synced at:
    Then strips leading blank lines left behind.
    """
    metadata_pattern = re.compile(
        r'^<!-- (?:sync from:|confluence version:|synced at:)[^\n]*\n?',
        re.MULTILINE,
    )
    result = metadata_pattern.sub('', md_text)
    return result.strip()
