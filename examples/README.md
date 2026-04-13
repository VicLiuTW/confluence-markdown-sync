# Examples — Confluence Markdown Sync Template Files

This directory contains template files that demonstrate the expected structure and conventions for specifications and implementation plans when using the confluence-markdown-sync tool.

## What These Templates Are For

When working with the confluence-markdown-sync tool, your local Markdown files must follow specific structural patterns to sync correctly with Confluence. These templates show:

- **template-spec.md** — A feature specification document (e.g., API design, module requirements)
- **template-plan.md** — An implementation plan document (e.g., phased rollout, tasks, timelines)

Both templates are generic examples (User Authentication, Notification System) that can be adapted for any product or domain.

## How to Use These Templates

1. **Copy** one of the template files to your project:
   ```bash
   cp examples/template-spec.md spec/your-feature-spec.md
   cp examples/template-plan.md spec/your-implementation-plan.md
   ```

2. **Rename and customize** the file to match your document:
   - Update section titles and content
   - Modify tables, lists, and code examples to your domain
   - Keep the structural layout (version table, horizontal rule separator, sections)

3. **Add to mapping** (if using `--sync` mode):
   ```bash
   python3 sync_confluence.py --mapping-add spec/your-feature-spec.md PAGE_ID
   ```

4. **Sync** to Confluence:
   ```bash
   python3 sync_confluence.py --sync
   ```

## Key Structural Rules

### Rule 1: No H1 Heading

Do NOT start your Markdown file with an H1 heading like `# Title`. Confluence displays the page title separately, so the Markdown body should start with section headings (H2 and below).

**Correct:**
```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
```

**Incorrect:**
```markdown
# User Authentication Module

## 文件版本
```

### Rule 2: Version Table Must Be First Section

The version history table must always be the first section (H2 heading `## 文件版本`). This allows the sync tool to:
- Detect and auto-increment version numbers on push
- Separate structural metadata from content when computing content hashes
- Track which versions have been synced

**Required format:**
```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2024-01-15 | Initial version |
```

### Rule 3: Horizontal Rule Separator

After the version table, insert a horizontal rule (`---`) to mark the separation between metadata and content. The tool uses this to:
- Exclude the version table from content hash computation
- Identify where the actual document content begins

```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2024-01-15 | Initial version |

---

## 1. 文件定位
```

### Rule 4: Image File References

When including images, use relative paths from the Markdown file location:

```markdown
![Alt text describing the image](../images/screenshot.png)
![Flow diagram](../images/process-flow.png)
```

During sync:
- **PUSH**: Local images are uploaded as Confluence attachments, and references are converted to Confluence storage format
- **PULL**: Confluence image tags are converted back to local path references or placeholder text

### Rule 5: Cross-References to Other Specs

Link to other specification documents using relative Markdown links:

```markdown
See [User Profile Management](../F1.2%20User%20Profile%20Management.md) for profile handling details.
```

When syncing to Confluence, these internal links work within the same space. For external links, use standard Confluence URLs:

```markdown
[Security Policy](https://yourorg.atlassian.net/wiki/spaces/DOCS/pages/123456)
```

### Rule 6: Table Format Conventions

Use standard Markdown tables with consistent column alignment:

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data A   | Data B   | Data C   |
```

The tool preserves tables during sync. Avoid:
- Inconsistent column separators
- Empty cells without spaces (use ` ` or `-`)
- Very wide tables (>80 characters per row) — wrap text instead

## File Structure Overview

Both templates follow this pattern:

1. **Version Table** (`## 文件版本`) — Metadata, auto-managed by sync tool
2. **Horizontal Rule** (`---`) — Separator
3. **Document Content** — Sections 1 onwards
   - Overview and positioning
   - Detailed specifications or implementation phases
   - Tables, code examples, checklists
   - Cross-references to other documents

See the templates for concrete examples.

## Language Notes

- **Table headers in Chinese** (`文件版本`, `版本`, `撰寫人`) — This is the tool's convention for version history tracking
- **Document content in English or Chinese** — Your choice; the examples use English for generic content
- **Bilingual support** — The sync tool works with both Chinese and English content

---

# Examples — confluence-markdown-sync 樣板檔案

此目錄包含示例檔案，展示如何使用 confluence-markdown-sync 工具時，本地 Markdown 檔案應遵循的結構與慣例。

## 樣板檔案說明

此目錄包含兩個樣板：

- **template-spec.md** — 功能規格文件（如 API 設計、模組需求）
- **template-plan.md** — 實作計畫文件（如分階段推出、任務、時程）

兩個樣板都是通用示例（使用者驗證、通知系統），可根據任何產品或領域改編。

## 使用方式

1. **複製** 樣板到你的專案：
   ```bash
   cp examples/template-spec.md spec/your-feature-spec.md
   cp examples/template-plan.md spec/your-implementation-plan.md
   ```

2. **重新命名並自訂** 檔案以符合你的文件：
   - 更新章節標題與內容
   - 修改表格、列表、程式碼範例符合你的領域
   - 保持結構版面（版本表、分隔線、小節）

3. **新增到對應** （若使用 `--sync` 模式）：
   ```bash
   python3 sync_confluence.py --mapping-add spec/your-feature-spec.md PAGE_ID
   ```

4. **同步** 到 Confluence：
   ```bash
   python3 sync_confluence.py --sync
   ```

## 重要結構規則

### 規則 1：不使用 H1 標題

不要在 Markdown 檔案開頭使用 H1 標題（如 `# 標題`）。Confluence 會單獨顯示頁面標題，所以 Markdown 內容應從 H2 或更低層級開始。

### 規則 2：版本表必須在最前面

版本紀錄表（`## 文件版本`）必須是第一個小節。

```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2024-01-15 | 初版 |
```

### 規則 3：版本表後加分隔線

版本表後必須加上 `---` 分隔線，標記表格與內容的分界。

```markdown
## 文件版本

...版本表...

---

## 1. 文件定位
```

### 規則 4：圖片檔案參考

使用相對路徑參考圖片：

```markdown
![圖片描述](../images/screenshot.png)
```

同步時：
- **PUSH**：本地圖片會上傳為 Confluence 附件
- **PULL**：Confluence 圖片標籤會轉換回本地路徑或佔位符

### 規則 5：跨文件參考

使用相對 Markdown 連結指向其他規格：

```markdown
詳見 [使用者檔案管理](../F1.2%20使用者檔案管理.md)。
```

### 規則 6：表格格式慣例

使用標準 Markdown 表格，欄位對齊一致：

```markdown
| 欄位 A | 欄位 B | 欄位 C |
|--------|--------|--------|
| 資料   | 資料   | 資料   |
```

## 更多資訊

詳見樣板檔案的實際例子，或參考主 README 的完整說明：
- [README.md](../README.md) — English documentation
- [README.zh-TW.md](../README.zh-TW.md) — 繁體中文說明
