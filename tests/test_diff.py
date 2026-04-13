import unittest
from sync_lib.diff import (
    compute_content_hash,
    parse_version_table,
    next_minor_version,
    append_version_entry,
    detect_change_type,
)

SAMPLE_DOC = """\
# 標題

內文段落

## 文件版本

| 版本 | 作者 | 日期 | 描述 |
| --- | --- | --- | --- |
| v1.0 | author | 2026-01-01 | 初始版本 |
| v1.5 | author | 2026-04-01 | 更新內容 |

---

## 其他章節

其他內文
"""

SAMPLE_DOC_NO_TABLE = """\
# 標題

只有內文，沒有版本表
"""


class TestContentHash(unittest.TestCase):
    def test_excludes_version_table(self):
        doc_v1 = """\
# 標題

內文

## 文件版本

| 版本 | 作者 | 日期 | 描述 |
| --- | --- | --- | --- |
| v1.0 | author | 2026-01-01 | 初始 |

---
"""
        doc_v2 = """\
# 標題

內文

## 文件版本

| 版本 | 作者 | 日期 | 描述 |
| --- | --- | --- | --- |
| v1.0 | author | 2026-01-01 | 初始 |
| v1.1 | author | 2026-02-01 | 新增 |

---
"""
        self.assertEqual(compute_content_hash(doc_v1), compute_content_hash(doc_v2))

    def test_different_content_different_hash(self):
        doc1 = "# 標題\n\n內文 A\n"
        doc2 = "# 標題\n\n內文 B\n"
        self.assertNotEqual(compute_content_hash(doc1), compute_content_hash(doc2))

    def test_no_version_table_hashes_everything(self):
        result = compute_content_hash(SAMPLE_DOC_NO_TABLE)
        self.assertTrue(result.startswith("sha256:"))


class TestParseVersionTable(unittest.TestCase):
    def test_extracts_latest_version(self):
        result = parse_version_table(SAMPLE_DOC)
        self.assertEqual(result["latest_version"], "v1.5")
        self.assertEqual(len(result["entries"]), 2)
        self.assertEqual(result["entries"][0]["version"], "v1.0")
        self.assertEqual(result["entries"][1]["version"], "v1.5")

    def test_no_version_table(self):
        result = parse_version_table(SAMPLE_DOC_NO_TABLE)
        self.assertIsNone(result["latest_version"])
        self.assertEqual(result["entries"], [])


class TestNextMinorVersion(unittest.TestCase):
    def test_increments_minor(self):
        self.assertEqual(next_minor_version("v1.5"), "v1.6")

    def test_increments_from_zero(self):
        self.assertEqual(next_minor_version("v2.0"), "v2.1")

    def test_single_number_adds_minor(self):
        self.assertEqual(next_minor_version("v1"), "v1.1")

    def test_none_returns_v0_1(self):
        self.assertEqual(next_minor_version(None), "v0.1")


class TestAppendVersionEntry(unittest.TestCase):
    def test_appends_to_existing_table(self):
        result = append_version_entry(SAMPLE_DOC, "v1.6", "2026-04-13", "新功能", author="tester")
        # New row is present
        self.assertIn("| v1.6 | tester | 2026-04-13 | 新功能 |", result)
        # Old rows still present
        self.assertIn("| v1.0 | author | 2026-01-01 | 初始版本 |", result)
        self.assertIn("| v1.5 | author | 2026-04-01 | 更新內容 |", result)
        # Content after table preserved
        self.assertIn("## 其他章節", result)
        self.assertIn("其他內文", result)


class TestDetectChangeType(unittest.TestCase):
    def _last_sync(self, hash_val="sha256:abc", version="v1.0"):
        return {"local_content_hash": hash_val, "confluence_version": version}

    def test_ok(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=True,
            last_sync=self._last_sync(),
            current_hash="sha256:abc",
            current_version="v1.0",
        )
        self.assertEqual(result, "OK")

    def test_push(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=True,
            last_sync=self._last_sync(),
            current_hash="sha256:different",
            current_version="v1.0",
        )
        self.assertEqual(result, "PUSH")

    def test_pull(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=True,
            last_sync=self._last_sync(),
            current_hash="sha256:abc",
            current_version="v1.1",
        )
        self.assertEqual(result, "PULL")

    def test_conflict(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=True,
            last_sync=self._last_sync(),
            current_hash="sha256:different",
            current_version="v1.1",
        )
        self.assertEqual(result, "CONFLICT")

    def test_new(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=True,
            last_sync=None,
            current_hash="sha256:abc",
            current_version="v1.0",
        )
        self.assertEqual(result, "NEW")

    def test_deleted_local(self):
        result = detect_change_type(
            local_exists=False,
            remote_exists=True,
            last_sync=self._last_sync(),
            current_hash="sha256:abc",
            current_version="v1.0",
        )
        self.assertEqual(result, "DELETED_LOCAL")

    def test_deleted_remote(self):
        result = detect_change_type(
            local_exists=True,
            remote_exists=False,
            last_sync=self._last_sync(),
            current_hash="sha256:abc",
            current_version="v1.0",
        )
        self.assertEqual(result, "DELETED_REMOTE")


if __name__ == "__main__":
    unittest.main()
