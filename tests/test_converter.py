"""Tests for sync_lib.converter module."""

import unittest

from sync_lib.converter import (
    confluence_html_to_md,
    extract_image_refs,
    md_to_confluence_html,
    strip_sync_metadata,
)


class TestMdToHtml(unittest.TestCase):
    def test_heading(self):
        result = md_to_confluence_html("# Title\n\nParagraph")
        self.assertIn("<h1>Title</h1>", result)
        self.assertIn("<p>Paragraph</p>", result)

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = md_to_confluence_html(md)
        self.assertIn("<table>", result)
        self.assertIn("<td>", result)

    def test_fenced_code(self):
        md = "```python\nprint('hello')\n```"
        result = md_to_confluence_html(md)
        self.assertIn("<code", result)
        self.assertIn("print('hello')", result)

    def test_image_converts_to_ac_image(self):
        md = "![screenshot](../images/shot.png)"
        result = md_to_confluence_html(md)
        self.assertIn('ri:filename="shot.png"', result)
        self.assertNotIn("<img", result)

    def test_external_image_preserved(self):
        md = "![logo](https://example.com/logo.png)"
        result = md_to_confluence_html(md)
        self.assertIn("https://example.com/logo.png", result)
        self.assertNotIn("ri:filename", result)


class TestHtmlToMd(unittest.TestCase):
    def test_heading(self):
        result = confluence_html_to_md("<h1>Title</h1>")
        self.assertIn("# Title", result)

    def test_ac_image_to_placeholder(self):
        html = '<ac:image><ri:attachment ri:filename="shot.png"/></ac:image>'
        result = confluence_html_to_md(html)
        self.assertIn("[圖片: shot.png]", result)


class TestExtractImageRefs(unittest.TestCase):
    def test_extracts_local_images(self):
        md = "![img1](../images/a.png)\n\nSome text\n\n![img2](./b.jpg)"
        refs = extract_image_refs(md)
        self.assertEqual(len(refs), 2)
        filenames = {r["filename"] for r in refs}
        self.assertIn("a.png", filenames)
        self.assertIn("b.jpg", filenames)
        paths = {r["path"] for r in refs}
        self.assertIn("../images/a.png", paths)
        self.assertIn("./b.jpg", paths)

    def test_ignores_external_urls(self):
        md = "![logo](https://example.com/logo.png)"
        refs = extract_image_refs(md)
        self.assertEqual(len(refs), 0)

    def test_empty_when_no_images(self):
        md = "Just some text with no images."
        refs = extract_image_refs(md)
        self.assertEqual(refs, [])


class TestStripSyncMetadata(unittest.TestCase):
    def test_strips_old_metadata(self):
        md = (
            "<!-- sync from: https://example.atlassian.net/wiki/spaces/DEMO/pages/123 -->\n"
            "<!-- confluence version: 5 -->\n"
            "<!-- synced at: 2026-04-10T12:00:00 -->\n"
            "\n"
            "# Real Content\n"
            "\n"
            "Body text here.\n"
        )
        result = strip_sync_metadata(md)
        self.assertNotIn("<!-- sync from:", result)
        self.assertNotIn("<!-- confluence version:", result)
        self.assertNotIn("<!-- synced at:", result)
        self.assertIn("# Real Content", result)
        self.assertIn("Body text here.", result)

    def test_no_metadata_unchanged(self):
        md = "# Normal Document\n\nNo metadata here.\n"
        result = strip_sync_metadata(md)
        self.assertEqual(result, md.strip())


if __name__ == "__main__":
    unittest.main()
