# confluence-markdown-sync

Bidirectional sync between local Markdown files and Confluence Cloud pages with automatic conflict detection, image handling, and version history management.

[README 繁體中文版本](README.zh-TW.md)

## Why This Tool?

Many teams maintain specs, design docs, and implementation plans on Confluence for collaboration, but find it hard to iterate quickly -- especially when working with AI assistants or local editors.

This tool bridges the gap:

- **Cloud to local**: Pull Confluence pages as Markdown files that AI tools (Claude, ChatGPT, Copilot, etc.) or any text editor can read and edit directly
- **Local to cloud**: Push your locally-edited Markdown back to Confluence, keeping your team in sync
- **Safe iteration**: The whitelist + conflict detection ensures you never accidentally overwrite changes made by teammates on Confluence

### Typical workflow

1. Pull specs from Confluence as Markdown
2. Feed Markdown files to an AI assistant for analysis, review, or rewriting
3. Edit locally (AI-assisted or manual) with your preferred tools
4. Push updated specs back to Confluence
5. Team reviews on Confluence as usual

This is especially useful for teams that haven't adopted AI-assisted workflows yet -- this tool lets you start using AI for document iteration without changing your team's existing Confluence-based process.

## Features

- **Bidirectional Sync**: Push local changes to Confluence, pull remote changes to local, or sync both directions with conflict detection
- **Whitelist-Based Scope Control**: Control which pages sync via `.sync_mapping.json` whitelist
- **Conflict Detection**: Automatic detection using content hash + Confluence page version to prevent accidental overwrites
- **Version History Management**: Auto-append version table entries on push, detect missing versions on pull
- **Image Sync**: Upload local images as attachments on push, download on pull
- **Confluence TOC Macro**: Auto-insert table of contents macro on push
- **Backward Compatible**: Legacy single-page pull mode still supported
- **Sync Plan Output**: Structured table showing PUSH/PULL/CONFLICT/OK status for each file before execution

## Requirements

- Python 3.10+
- `markdown` package
- `markdownify` package
- Confluence Cloud account with API token

## Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd confluence-markdown-sync
   ```

2. Install dependencies:
   ```bash
   pip install markdown markdownify
   ```

3. Create `.env` file in the project root:
   ```
   CONFLUENCE_BASE_URL=https://your-domain.atlassian.net
   CONFLUENCE_EMAIL=your.email@example.com
   CONFLUENCE_API_TOKEN=your_api_token
   ```

4. Create or initialize `.sync_mapping.json`:
   ```bash
   # Option A: Manual creation
   # See "Configuration" section below

   # Option B: Use --mapping-add to build whitelist interactively
   python3 sync_confluence.py --mapping-add docs/spec.md 123456789
   ```

## Quick Start

### Bidirectional Sync (Main Mode)

Sync all whitelisted pages with automatic conflict detection:

```bash
python3 sync_confluence.py --sync
```

This will:
1. Display a sync plan showing PUSH, PULL, CONFLICT, or OK status for each file
2. Detect changes using content hash and page version
3. Handle conflicts if the same file was modified both locally and remotely
4. Append version history entries on push
5. Download new/updated images

### Legacy Single-Page Pull Mode

Pull a single page from Confluence (no whitelist required):

```bash
python3 sync_confluence.py "https://your-domain.atlassian.net/wiki/spaces/V/pages/123456789"
```

Supports various URL formats:
- Full page URL: `https://domain.atlassian.net/wiki/spaces/SPACE/pages/PAGE_ID`
- Short link: `https://domain.atlassian.net/wiki/x/SHORT_ID`
- Query parameter: `https://domain.atlassian.net/wiki/spaces/V?pageId=PAGE_ID`

Options:
- `--target-dir DIRNAME` — Save to specific directory (default: `spec/`)
- `--dry-run` — Preview changes without writing
- `--download-images` — Download attachments during pull
- `--images-dir DIRNAME` — Save images to custom directory

### Manage Whitelist

Add a file to the sync whitelist:
```bash
python3 sync_confluence.py --mapping-add local/path/file.md 123456789
```

List all whitelisted mappings:
```bash
python3 sync_confluence.py --mapping-list
```

Remove a mapping by page ID:
```bash
python3 sync_confluence.py --mapping-remove 123456789
```

### Batch Image Download (Legacy)

Download images for all markdown files in a directory:
```bash
python3 sync_confluence.py --batch-images spec/admin
```

## Configuration

### .sync_mapping.json Structure

```json
{
  "meta": {
    "confluence_base_url": "https://your-domain.atlassian.net",
    "confluence_folder_id": "987654",
    "local_dir": "spec/docs"
  },
  "pages": {
    "123456789": {
      "confluence_title": "Page Title",
      "local_file": "F1.0 Spec Name.md",
      "last_sync": {
        "time": "2026-04-13T10:00:00Z",
        "confluence_version": 5,
        "local_content_hash": "sha256:abc123..."
      }
    }
  }
}
```

**Field Descriptions:**

- `meta.confluence_base_url` — Your Confluence Cloud instance URL
- `meta.confluence_folder_id` — Parent page ID for organizing all synced pages (optional)
- `meta.local_dir` — Base directory for all synced markdown files
- `pages` — Whitelist of page mappings (page_id → metadata)
- `pages[id].confluence_title` — Page title in Confluence (auto-filled after first sync)
- `pages[id].local_file` — Path relative to `meta.local_dir`
- `pages[id].last_sync` — Timestamp, version, and content hash from last successful sync

### Confluence API Token

To generate an API token:
1. Log in to Confluence
2. Go to your account settings
3. Select "Security" → "API tokens"
4. Create a new API token
5. Copy the token and add to `.env`

## Sync Plan Output Example

```
╔════════╦═══════════════╦══════════════════╗
║ ACTION ║ FILE          ║ REASON           ║
╠════════╬═══════════════╬══════════════════╣
║ ↑ PUSH ║ spec-a.md     ║ Local change     ║
║ ↓ PULL ║ spec-b.md     ║ Remote change    ║
║ ✓ OK   ║ spec-c.md     ║ No changes       ║
╚════════╩═══════════════╩══════════════════╝
```

## Version History Table Format

The tool automatically manages a version history table at the top of each markdown file. Format:

```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2026-04-10 | Initial version |
| v1.1 | author | 2026-04-12 | Updated content |
```

When pushing changes:
- If the version table exists, a new entry is appended with incremented version (v1.0 → v1.1)
- Author name is pulled from Confluence API metadata
- Current date is auto-filled
- Description is prompted from user

When pulling:
- Missing rows (based on local version history) are detected
- Tool alerts if remote page has newer versions not in local file

## Image Handling

### Local Images (Push)

In markdown files, reference local images using relative paths:

```markdown
![Alt text](../images/screenshot.png)
```

When pushing:
1. Tool scans for local image references
2. Uploads each image as an attachment to the Confluence page
3. Replaces references with Confluence ac:image tags in storage format

### Remote Images (Pull)

When pulling:
1. Confluence ac:image tags are converted to placeholder text: `[圖片: filename]`
2. Use `--download-images` to also download attachments to local disk
3. Downloaded images are saved to `--images-dir` (default: `spec/docs/images`)

## Module Structure

```
sync_confluence.py          CLI entry point, argument parsing, sync orchestration
sync_lib/
  __init__.py               Package marker
  mapping.py                Whitelist CRUD operations on .sync_mapping.json
  confluence_api.py         Confluence REST API wrapper
  converter.py              Bidirectional HTML ↔ Markdown conversion
  diff.py                   Conflict detection, sync plan generation, version table ops
tests/
  test_mapping.py           Unit tests for whitelist operations
  test_converter.py         Unit tests for HTML ↔ Markdown conversion
  test_diff.py              Unit tests for change detection and version table parsing
```

## Conflict Resolution

When `--sync` detects both local and remote changes to the same file:

1. Tool displays conflict alert with details
2. User is prompted to choose:
   - `LOCAL` — Keep local version, overwrite remote
   - `REMOTE` — Keep remote version, overwrite local
   - `MANUAL` — Exit and let user merge manually
3. After resolution, run `--sync` again to complete push/pull

Conflicts are detected using:
- Content hash of markdown (excluding version table)
- Confluence page version number

## Examples

### Example 1: Set Up a New Project

```bash
# Initialize whitelist
python3 sync_confluence.py --mapping-add "spec/getting-started.md" 123456

# Configure metadata
# Edit .sync_mapping.json to set confluence_base_url, confluence_folder_id, local_dir

# Run first sync
python3 sync_confluence.py --sync
```

### Example 2: Pull Single Page (Legacy Mode)

```bash
python3 sync_confluence.py \
  "https://my-org.atlassian.net/wiki/spaces/PROD/pages/555666" \
  --target-dir "docs/api" \
  --download-images
```

### Example 3: Sync With Image Support

```bash
# Add page to whitelist
python3 sync_confluence.py --mapping-add "spec/design.md" 789012

# Sync with image download
python3 sync_confluence.py --sync
```

## Troubleshooting

### Error: "找不到 .env"
Create `.env` file with required credentials. See "Installation" section.

### Error: "認證失敗"
Check `.env` has correct `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`.

### Error: "無法從 URL 提取 page ID"
Use a full Confluence page URL like `https://domain.atlassian.net/wiki/spaces/SPACE/pages/PAGE_ID`.

### Conflict Detected on Sync
Edit `.sync_mapping.json` manually to reset `last_sync` for the conflicted page, or resolve manually and run `--sync` again.

### Version Table Not Detected
Ensure the markdown file contains exactly:
```markdown
## 文件版本

| 版本 | ... |
```
(Case-sensitive, exact table structure required)

## Testing

Run unit tests:

```bash
python3 -m pytest tests/ -v
```

Run tests for specific module:

```bash
python3 -m pytest tests/test_mapping.py -v
python3 -m pytest tests/test_converter.py -v
python3 -m pytest tests/test_diff.py -v
```

## License

MIT

## Contributing

Contributions welcome. Please ensure:
- All tests pass: `pytest tests/`
- Python code follows PEP 8
- New features include unit tests
