"""Tests for sync_lib.mapping module."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from sync_lib.mapping import (
    add_entry,
    list_entries,
    load_mapping,
    remove_entry,
    resolve_local_file,
    save_mapping,
)


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mapping_file = os.path.join(self.tmpdir, ".sync_mapping.json")

    def test_load_nonexistent_returns_empty(self):
        data = load_mapping(self.mapping_file)
        self.assertIn("meta", data)
        self.assertIn("pages", data)
        self.assertEqual(data["meta"]["confluence_base_url"], "")
        self.assertEqual(data["meta"]["confluence_folder_id"], "")
        self.assertEqual(data["meta"]["local_dir"], "")
        self.assertEqual(data["pages"], {})

    def test_save_and_load_roundtrip(self):
        original = {
            "meta": {
                "confluence_base_url": "https://example.atlassian.net",
                "confluence_folder_id": "12345",
                "local_dir": "/tmp/docs",
            },
            "pages": {
                "111": {
                    "local_file": "foo.md",
                    "confluence_title": "Foo Page",
                    "last_sync": "2026-01-01T00:00:00",
                }
            },
        }
        save_mapping(original, self.mapping_file)
        loaded = load_mapping(self.mapping_file)
        self.assertEqual(loaded, original)
        # Verify trailing newline
        with open(self.mapping_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.endswith("\n"))

    def test_add_entry(self):
        # Create a real local file
        local_file = "test_doc.md"
        local_path = os.path.join(self.tmpdir, local_file)
        Path(local_path).write_text("# Test", encoding="utf-8")

        # Set up mapping with local_dir pointing to tmpdir
        data = load_mapping(self.mapping_file)
        data["meta"]["local_dir"] = self.tmpdir
        save_mapping(data, self.mapping_file)

        add_entry(self.mapping_file, local_file, "page-001")

        loaded = load_mapping(self.mapping_file)
        self.assertIn("page-001", loaded["pages"])
        self.assertEqual(loaded["pages"]["page-001"]["local_file"], local_file)
        self.assertIsNone(loaded["pages"]["page-001"]["last_sync"])

    def test_remove_entry(self):
        data = {
            "meta": {"confluence_base_url": "", "confluence_folder_id": "", "local_dir": ""},
            "pages": {
                "page-abc": {
                    "local_file": "a.md",
                    "confluence_title": "A",
                    "last_sync": None,
                }
            },
        }
        save_mapping(data, self.mapping_file)

        remove_entry(self.mapping_file, "page-abc")

        loaded = load_mapping(self.mapping_file)
        self.assertNotIn("page-abc", loaded["pages"])

    def test_remove_nonexistent_raises(self):
        save_mapping(load_mapping(self.mapping_file), self.mapping_file)
        with self.assertRaises(KeyError):
            remove_entry(self.mapping_file, "nonexistent-id")

    def test_list_entries(self):
        data = {
            "meta": {"confluence_base_url": "", "confluence_folder_id": "", "local_dir": ""},
            "pages": {
                "p1": {
                    "local_file": "one.md",
                    "confluence_title": "One",
                    "last_sync": "2026-01-01T00:00:00",
                },
                "p2": {
                    "local_file": "two.md",
                    "confluence_title": "Two",
                    "last_sync": None,
                },
            },
        }
        save_mapping(data, self.mapping_file)

        entries = list_entries(self.mapping_file)
        self.assertEqual(len(entries), 2)

        page_ids = {e["page_id"] for e in entries}
        self.assertIn("p1", page_ids)
        self.assertIn("p2", page_ids)

        p1 = next(e for e in entries if e["page_id"] == "p1")
        self.assertEqual(p1["confluence_title"], "One")
        self.assertEqual(p1["local_file"], "one.md")
        self.assertEqual(p1["last_sync"], "2026-01-01T00:00:00")

        p2 = next(e for e in entries if e["page_id"] == "p2")
        self.assertIsNone(p2["last_sync"])

    def test_resolve_local_file(self):
        meta = {"local_dir": "/some/base/dir"}
        entry = {"local_file": "subdir/doc.md"}
        result = resolve_local_file(meta, entry)
        self.assertEqual(result, "/some/base/dir/subdir/doc.md")

    def test_add_entry_nonexistent_file_raises(self):
        data = load_mapping(self.mapping_file)
        data["meta"]["local_dir"] = self.tmpdir
        save_mapping(data, self.mapping_file)

        with self.assertRaises(FileNotFoundError):
            add_entry(self.mapping_file, "does_not_exist.md", "page-999")


if __name__ == "__main__":
    unittest.main()
