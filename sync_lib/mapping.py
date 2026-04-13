"""Whitelist mapping CRUD for .sync_mapping.json."""

import json
import os
from pathlib import Path


def load_mapping(mapping_file: str) -> dict:
    """Load mapping from JSON. Return empty structure if file doesn't exist."""
    if not os.path.exists(mapping_file):
        return {
            "meta": {
                "confluence_base_url": "",
                "confluence_folder_id": "",
                "local_dir": "",
            },
            "pages": {},
        }
    with open(mapping_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_mapping(data: dict, mapping_file: str) -> None:
    """Write JSON with ensure_ascii=False, indent=2, trailing newline."""
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_entry(mapping_file: str, local_file: str, page_id: str) -> None:
    """Load mapping, validate local file exists, add to pages with last_sync: None, save."""
    data = load_mapping(mapping_file)
    meta = data.get("meta", {})
    local_dir = meta.get("local_dir", "")
    full_path = Path(local_dir) / local_file
    if not full_path.exists():
        raise FileNotFoundError(f"Local file not found: {full_path}")
    data["pages"][page_id] = {
        "local_file": local_file,
        "confluence_title": "",
        "last_sync": None,
    }
    save_mapping(data, mapping_file)


def remove_entry(mapping_file: str, page_id: str) -> None:
    """Remove entry by page_id. Raise KeyError if not found."""
    data = load_mapping(mapping_file)
    if page_id not in data["pages"]:
        raise KeyError(f"page_id not found: {page_id}")
    del data["pages"][page_id]
    save_mapping(data, mapping_file)


def list_entries(mapping_file: str) -> list:
    """Return list of {page_id, confluence_title, local_file, last_sync}."""
    data = load_mapping(mapping_file)
    result = []
    for page_id, entry in data["pages"].items():
        result.append({
            "page_id": page_id,
            "confluence_title": entry.get("confluence_title", ""),
            "local_file": entry.get("local_file", ""),
            "last_sync": entry.get("last_sync"),
        })
    return result


def resolve_local_file(meta: dict, entry: dict) -> str:
    """Return str(Path(meta['local_dir']) / entry['local_file'])."""
    return str(Path(meta["local_dir"]) / entry["local_file"])
