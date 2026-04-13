import hashlib
import re
from datetime import datetime


def _strip_version_table(md_text: str) -> str:
    """Internal helper. Walk lines, skip from '## 文件版本' to '---'."""
    lines = md_text.splitlines(keepends=True)
    result = []
    in_version_block = False
    for line in lines:
        stripped = line.rstrip('\n').rstrip('\r')
        if stripped == "## 文件版本":
            in_version_block = True
            continue
        if in_version_block:
            if stripped == "---":
                in_version_block = False
                continue
            continue
        result.append(line)
    return "".join(result)


def compute_content_hash(md_text: str) -> str:
    """SHA-256 of content EXCLUDING the version table block."""
    stripped = _strip_version_table(md_text)
    hex_digest = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
    return f"sha256:{hex_digest}"


def parse_version_table(md_text: str) -> dict:
    """Return dict with latest_version and entries parsed from version table."""
    lines = md_text.splitlines()
    in_version_block = False
    entries = []
    for line in lines:
        stripped = line.strip()
        if stripped == "## 文件版本":
            in_version_block = True
            continue
        if in_version_block:
            if stripped == "---":
                break
            # Skip non-table lines and empty lines
            if not stripped.startswith("|"):
                continue
            # Skip header row (first cell is 版本) and separator row (cells are ---)
            first_cell = stripped.strip("|").split("|")[0].strip() if "|" in stripped else ""
            if first_cell == "版本" or re.search(r'\|\s*-+\s*\|', stripped):
                continue
            # Parse pipe-delimited row
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            if len(parts) >= 4:
                entries.append({
                    "version": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "description": parts[3],
                })
    latest_version = entries[-1]["version"] if entries else None
    return {"latest_version": latest_version, "entries": entries}


def next_minor_version(version: str | None) -> str:
    """Increment the minor version. v1.5→v1.6, v2.0→v2.1, v1→v1.1, None→v0.1."""
    if version is None:
        return "v0.1"
    # Strip 'v' prefix
    bare = version.lstrip("v")
    parts = bare.split(".")
    if len(parts) == 1:
        # Single number like "1" → "1.1"
        return f"v{parts[0]}.1"
    # Increment last part
    last = int(parts[-1]) + 1
    parts[-1] = str(last)
    return "v" + ".".join(parts)


def append_version_entry(md_text: str, version: str, date: str, summary: str, author: str = "author") -> str:
    """Insert new version row at end of version table.

    Strategy: find the last '|' line within the version table section,
    insert the new row right after it.
    """
    new_row = f"| {version} | {author} | {date} | {summary} |"
    lines = md_text.split("\n")

    # Find the version table section and the last table row
    in_version_section = False
    last_table_row_idx = None

    for i, line in enumerate(lines):
        if re.match(r"^##\s+文件版本", line):
            in_version_section = True
            continue
        if in_version_section:
            if line.strip().startswith("|"):
                last_table_row_idx = i
            elif line.strip() == "---" or (line.strip() == "" and last_table_row_idx is not None):
                # End of table section
                break

    if last_table_row_idx is not None:
        lines.insert(last_table_row_idx + 1, new_row)
    else:
        # No table found, append at end
        lines.append(new_row)

    return "\n".join(lines)


def detect_change_type(
    local_exists: bool,
    remote_exists: bool,
    last_sync: dict | None,
    current_hash: str,
    current_version: str | None,
) -> str:
    """Determine the sync action needed."""
    if last_sync is None:
        return "NEW"
    if not local_exists:
        return "DELETED_LOCAL"
    if not remote_exists:
        return "DELETED_REMOTE"

    hash_differs = current_hash != last_sync.get("local_content_hash")
    version_differs = current_version != last_sync.get("confluence_version")

    if hash_differs and version_differs:
        return "CONFLICT"
    if hash_differs:
        return "PUSH"
    if version_differs:
        return "PULL"
    return "OK"


# Action symbol mapping
_ACTION_SYMBOLS = {
    "PUSH": "↑",
    "PULL": "↓",
    "CONFLICT": "⚡",
    "NEW": "+",
    "DELETED_LOCAL": "✗",
    "DELETED_REMOTE": "✗",
    "OK": "✓",
}


def generate_sync_plan(changes: list[dict]) -> str:
    """Format sync plan as a bordered table with summary."""
    if not changes:
        return "No changes detected."

    # Determine column widths
    header_action = "ACTION"
    header_file = "FILE"
    header_reason = "REASON"

    col_action = max(len(header_action), max(len(c["action"]) + 2 for c in changes))
    col_file = max(len(header_file), max(len(c["local_file"]) for c in changes))
    col_reason = max(len(header_reason), max(len(c["reason"]) for c in changes))

    border_top = "╔" + "═" * (col_action + 2) + "╦" + "═" * (col_file + 2) + "╦" + "═" * (col_reason + 2) + "╗"
    border_mid = "╠" + "═" * (col_action + 2) + "╬" + "═" * (col_file + 2) + "╬" + "═" * (col_reason + 2) + "╣"
    border_row = "╟" + "─" * (col_action + 2) + "╫" + "─" * (col_file + 2) + "╫" + "─" * (col_reason + 2) + "╢"
    border_bot = "╚" + "═" * (col_action + 2) + "╩" + "═" * (col_file + 2) + "╩" + "═" * (col_reason + 2) + "╝"

    def row(a, f, r):
        return "║ " + a.ljust(col_action) + " ║ " + f.ljust(col_file) + " ║ " + r.ljust(col_reason) + " ║"

    lines = [border_top]
    lines.append(row(header_action, header_file, header_reason))
    lines.append(border_mid)

    for idx, change in enumerate(changes):
        action = change["action"]
        symbol = _ACTION_SYMBOLS.get(action, "?")
        action_display = f"{symbol} {action}"
        lines.append(row(action_display, change["local_file"], change["reason"]))
        # Add images sub-rows if present
        images = change.get("images") or []
        for img in images:
            lines.append(row("", f"  {img}", ""))
        if idx < len(changes) - 1:
            lines.append(border_row)

    lines.append(border_bot)

    # Summary counts
    counts: dict[str, int] = {}
    for c in changes:
        counts[c["action"]] = counts.get(c["action"], 0) + 1

    summary_parts = [f"{v} {k}" for k, v in sorted(counts.items())]
    lines.append("Summary: " + ", ".join(summary_parts))

    return "\n".join(lines)
