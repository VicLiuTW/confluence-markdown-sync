# Confluence Markdown Sync

[README 也有英文版本](README.md)

雙向同步工具，在本地 Markdown 文件與 Confluence Cloud 頁面之間自動同步，支援衝突偵測、版本管理與圖片同步。

## 為什麼需要這個工具？

許多團隊在 Confluence 上維護規格文件、設計文件和實作計畫，方便協作。但當需要快速迭代文件內容時——特別是搭配 AI 助手或本地編輯器——Confluence 的線上編輯器就顯得不夠靈活。

這個工具打通了兩端：

- **雲端到本地**：將 Confluence 頁面拉取為 Markdown 文件，讓 AI 工具（Claude、ChatGPT、Copilot 等）或任何文字編輯器都能直接讀取和編輯
- **本地到雲端**：將本地編輯完成的 Markdown 推送回 Confluence，團隊成員在 Confluence 上即可看到最新版本
- **安全迭代**：白名單 + 衝突偵測確保不會意外覆蓋團隊成員在 Confluence 上的修改

### 典型工作流程

1. 從 Confluence 拉取規格文件為 Markdown
2. 將 Markdown 檔案提供給 AI 助手進行分析、審查或改寫
3. 在本地使用偏好的工具進行編輯（AI 輔助或手動）
4. 將更新後的文件推送回 Confluence
5. 團隊在 Confluence 上照常 review

這對於尚未導入 AI 協作流程的團隊特別有用——不需要改變團隊現有的 Confluence 工作流程，就能開始用 AI 進行文件迭代。

## 功能特性

- **雙向同步** — 自動偵測本地與遠端變更，支援 PUSH/PULL/CONFLICT 三種同步模式
- **白名單制管理** — 透過 `.sync_mapping.json` 精細控制同步範圍，免去無意中修改不該更新的文件
- **衝突偵測** — 基於 SHA-256 內容雜湊與 Confluence 頁面版本號，自動識別本地與遠端同時修改的情況
- **版本紀錄表格** — 自動維護文件版本表（PUSH 時遞增版號，PULL 時偵測缺漏），確保版本追蹤
- **圖片同步** — PUSH 時上傳本地圖片為附件，PULL 時下載遠端圖片，自動轉換 Markdown 圖片語法
- **Confluence TOC 巨集** — PUSH 時自動插入文件目錄巨集（Table of Contents）
- **向後相容** — 保留單頁拉取模式（舊用法），已有的流程不中斷

## 技術堆棧

- **Python 3.10+**
- **依賴套件**：`markdown`, `markdownify`
- **Confluence REST API v1** — 透過 Basic Auth (.env 設定)
- **內部模組架構**：
  - `sync_confluence.py` — CLI 入口、同步調度
  - `sync_lib/mapping.py` — .sync_mapping.json 讀寫、白名單管理
  - `sync_lib/confluence_api.py` — Confluence REST API 封裝
  - `sync_lib/converter.py` — HTML ↔ Markdown 雙向轉換
  - `sync_lib/diff.py` — 衝突偵測、同步計畫、版本表操作
  - `tests/` — 單元測試

## 安裝與設定

### 1. 複製此專案

```bash
git clone <repo-url>
cd confluence-markdown-sync
```

### 2. 安裝依賴

```bash
pip3 install -r requirements.txt
```

或直接安裝套件：

```bash
pip3 install markdown markdownify
```

### 3. 設定 `.env`

在專案根目錄建立 `.env` 檔案，包含 Confluence 認證資訊：

```env
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net
CONFLUENCE_EMAIL=your.email@company.com
CONFLUENCE_API_TOKEN=your_api_token_here
```

如何取得 API Token：
1. 前往 https://id.atlassian.com/manage-profile/security/api-tokens
2. 點擊「建立 API Token」
3. 選擇「傳統 API Token」，輸入標籤名稱，點擊「建立」
4. 複製並貼到 `.env` 中的 `CONFLUENCE_API_TOKEN`

**注意**：`.env` 已加入 `.gitignore`，絕不會提交到版控。

### 4. 建立 `.sync_mapping.json`

有兩種方式建立同步對應：

#### 方式 A：手動編輯

在專案根目錄建立 `.sync_mapping.json`：

```json
{
  "meta": {
    "confluence_base_url": "https://your-domain.atlassian.net",
    "confluence_folder_id": "folder_id_or_space_id",
    "local_dir": "docs/specs"
  },
  "pages": {
    "PAGE_ID": {
      "confluence_title": "Page Title",
      "local_file": "spec-file.md",
      "last_sync": null
    }
  }
}
```

#### 方式 B：透過 CLI 指令

```bash
# 新增對應（會自動驗證本地文件存在）
python3 sync_confluence.py --mapping-add docs/specs/spec-01.md 123456789

# 查看所有對應
python3 sync_confluence.py --mapping-list

# 移除對應
python3 sync_confluence.py --mapping-remove 123456789
```

## 使用方式

### 主要用法：雙向同步

```bash
python3 sync_confluence.py --sync
```

此指令會：
1. 讀取 `.sync_mapping.json` 中的所有對應
2. 比較本地與 Confluence 版本，產生同步計畫
3. 顯示衝突表格與建議動作
4. 逐個確認或詢問用戶（衝突情況下）
5. 執行 PUSH/PULL 操作

同步計畫表示例：

```
╔════════╦═══════════════╦══════════════╗
║ ACTION ║ FILE          ║ REASON       ║
╠════════╬═══════════════╬══════════════╣
║ ↑ PUSH ║ spec-01.md    ║ 本地修改      ║
║ ↓ PULL ║ spec-02.md    ║ 遠端修改      ║
║ ✓ OK   ║ spec-03.md    ║ 無變更        ║
║ ⚡ CONFLICT ║ spec-04.md ║ 兩端都修改     ║
╚════════╩═══════════════╩══════════════╝
Summary: 1 CONFLICT, 1 OK, 1 PULL, 1 PUSH
```

**動作說明**：
- `↑ PUSH` — 本地有修改、遠端無變更 → 上傳到 Confluence
- `↓ PULL` — 本地無修改、遠端有變更 → 下載到本地
- `✓ OK` — 雙方無變更 → 跳過
- `⚡ CONFLICT` — 本地與遠端同時修改 → 需用戶確認
- `+` — 新增的頁面映射
- `✗` — 刪除（本地或遠端檔案不存在）

### 舊功能：單頁拉取（向後相容）

```bash
# 從 Confluence 拉取單一頁面到本地
python3 sync_confluence.py "<confluence_url>"

# 指定目標目錄
python3 sync_confluence.py "<confluence_url>" --target-dir "docs/specs"

# 預覽（不寫入檔案）
python3 sync_confluence.py "<confluence_url>" --dry-run
```

支援的 URL 格式：
- 標準 URL：`https://your-domain.atlassian.net/wiki/spaces/V/pages/4554782/PAGE_NAME`
- 短連結：`https://your-domain.atlassian.net/wiki/x/AbCdEf`

### 圖片同步

#### 自動圖片同步（通過 --sync）

```bash
python3 sync_confluence.py --sync
```

PUSH 時會自動上傳 Markdown 中的本地圖片引用（`![alt](path/to/image.png)`）為 Confluence 附件。

PULL 時會自動下載 Confluence 中的圖片並保存到本地。

#### 批次下載圖片（舊功能）

```bash
# 批次下載指定目錄中所有頁面的圖片
python3 sync_confluence.py --batch-images "spec/docs"
```

## 同步邏輯與衝突偵測

### 變更偵測表

| 本地有無修改 | 遠端有無修改 | 判定結果 | 建議動作 |
|-----------|----------|--------|--------|
| 無 | 無 | OK | 跳過，無變更 |
| 有 | 無 | PUSH | 上傳本地版本到 Confluence |
| 無 | 有 | PULL | 下載遠端版本到本地 |
| 有 | 有 | CONFLICT | 詢問用戶，可選擇 PUSH/PULL/KEEP |

### 內容雜湊計算

系統使用 SHA-256 雜湊來偵測本地內容變更，計算時**排除版本紀錄表格**，避免因版本更新而誤判內容修改。

```python
import hashlib
from sync_lib.diff import compute_content_hash

hash_value = compute_content_hash(markdown_text)
# 輸出：sha256:abc123...
```

### 版本號遞增

PUSH 時會自動遞增文件版本號，遵循「小版號遞增」規則：

- `v1.0` → `v1.1` → `v1.2` ...
- `v2.5` → `v2.6`
- `None` → `v0.1` （首次提交）

## 版本紀錄表格格式

文件中應包含以下格式的版本表：

```markdown
## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2026-04-10 | 初版 |
| v1.1 | author | 2026-04-12 | 修正冗餘內容 |

---
```

**重要**：版本表後必須加上 `---` 分隔線，標記表格結束。

### PUSH 時行為

- 系統自動計算新版號（遞增小版號）
- 將新行追加至版本表
- 新行格式：`| {new_version} | author | {date} | {summary} |`
- 需用戶提供摘要說明

### PULL 時行為

- 系統不修改版本表內容
- 若 Confluence 中的內容有更新但版本表未變，系統會提示用戶

## .sync_mapping.json 結構

```json
{
  "meta": {
    "confluence_base_url": "https://your-domain.atlassian.net",
    "confluence_folder_id": "123456",
    "local_dir": "docs/specs"
  },
  "pages": {
    "PAGE_ID_1": {
      "confluence_title": "頁面標題",
      "local_file": "local-spec-file.md",
      "last_sync": {
        "time": "2026-04-13T10:00:00",
        "confluence_version": 5,
        "local_content_hash": "sha256:abc123..."
      }
    },
    "PAGE_ID_2": {
      "confluence_title": "另一個頁面",
      "local_file": "another-spec.md",
      "last_sync": null
    }
  }
}
```

### 欄位說明

- `meta.confluence_base_url` — Confluence 實例基底 URL
- `meta.confluence_folder_id` — Space ID 或 Folder ID（可選，用於分類）
- `meta.local_dir` — 本地文件所在目錄
- `pages` — 頁面對應表，key 為 Confluence page ID
  - `confluence_title` — Confluence 中的頁面標題
  - `local_file` — 相對於 `local_dir` 的本地文件名
  - `last_sync` — 上次同步記錄（首次為 null）
    - `time` — 同步時間（ISO 8601 格式）
    - `confluence_version` — 上次同步時的 Confluence 頁面版本號
    - `local_content_hash` — 上次同步時的本地內容雜湊

## 圖片語法

### Markdown 圖片引用

本工具支援標準 Markdown 圖片語法：

```markdown
![替代文字](相對路徑或URL)
```

**例**：
```markdown
![流程圖](../images/process-flow.png)
![外部圖片](https://example.com/image.png)
```

### PUSH 時的轉換

- **本地相對路徑** `![alt](./images/img.png)` → Confluence ac:image 標籤（附件引用）
- **外部 HTTP/HTTPS URL** → 保持 HTML img 標籤

### PULL 時的轉換

- **Confluence ac:image 標籤** → 保留為 `[圖片: filename]` 純文字提示

## 命令列參考

### 雙向同步

```bash
python3 sync_confluence.py --sync
```

### 管理對應

```bash
# 新增本地文件與 Confluence 頁面的對應
python3 sync_confluence.py --mapping-add <local_file> <page_id>

# 列出所有對應（表格格式）
python3 sync_confluence.py --mapping-list

# 移除對應
python3 sync_confluence.py --mapping-remove <page_id>
```

### 舊用法：單頁拉取

```bash
# 從 URL 拉取單一頁面
python3 sync_confluence.py "<confluence_url>"

# 指定目標目錄
python3 sync_confluence.py "<confluence_url>" --target-dir "docs/specs"

# 預覽（不寫入）
python3 sync_confluence.py "<confluence_url>" --dry-run

# 下載圖片
python3 sync_confluence.py "<confluence_url>" --download-images

# 批次下載圖片
python3 sync_confluence.py --batch-images "spec/docs"
```

## 工作流範例

### 場景 1：初次同步多個 Confluence 頁面

```bash
# 1. 準備本地目錄與檔案
mkdir -p docs/specs
touch docs/specs/spec-a.md docs/specs/spec-b.md

# 2. 逐一新增對應
python3 sync_confluence.py --mapping-add docs/specs/spec-a.md 123456789
python3 sync_confluence.py --mapping-add docs/specs/spec-b.md 123456790

# 3. 驗證對應
python3 sync_confluence.py --mapping-list

# 4. 執行首次同步（從 Confluence 拉取內容）
python3 sync_confluence.py --sync
```

### 場景 2：編輯本地檔案並上傳

```bash
# 1. 編輯本地 Markdown 檔案
vim docs/specs/spec-a.md

# 2. 執行同步
python3 sync_confluence.py --sync

# 3. 系統會偵測到本地修改，顯示同步計畫
# 4. 確認上傳，系統會
#    - 遞增版號（v1.0 → v1.1）
#    - 更新版本表
#    - 上傳到 Confluence
```

### 場景 3：處理衝突

```bash
# 同時修改了本地與 Confluence 的同一頁面
python3 sync_confluence.py --sync

# 系統偵測到衝突，顯示：
# ⚡ CONFLICT | spec-a.md | 兩端都修改

# 系統會詢問：
# [?] spec-a.md 發生衝突。選擇動作：
#   [p] push (本地版本)
#   [l] pull (遠端版本)
#   [k] keep (保持本地不動)

# 根據需求選擇，系統隨後執行相應動作
```

## 環境變數

系統從 `.env` 檔案讀取以下變數：

| 變數名 | 用途 | 例 |
|--------|------|-----|
| `CONFLUENCE_BASE_URL` | Confluence 實例基底 URL | `https://your-domain.atlassian.net` |
| `CONFLUENCE_EMAIL` | 登入電子郵件 | `your.email@company.com` |
| `CONFLUENCE_API_TOKEN` | API Token | `your-api-token` |

## 常見問題

### Q: 如何避免誤刪檔案？

A: 本工具採用**白名單制**，只同步 `.sync_mapping.json` 中列出的頁面。未列出的 Confluence 頁面與本地檔案不會被觸及。

### Q: 如何恢復誤刪的版本？

A: 本工具不執行自動刪除。若本地檔案被意外刪除，可從 Git 歷史恢復；若 Confluence 被意外覆蓋，可從 Confluence 的版本歷史恢復。

### Q: 支援多人協作嗎？

A: 支援，但需遵循規則：
- 不同人編輯不同檔案時不會衝突
- 同一檔案的同時修改會被偵測為衝突，需人工確認

### Q: 如何同步圖片？

A: 自動同步。PUSH 時，Markdown 中的本地圖片引用會被上傳為 Confluence 附件；PULL 時，遠端圖片會被下載到本地。

### Q: 版本號怎麼重置？

A: 不建議手動修改版本號。若確需重置，可編輯 `.sync_mapping.json` 中的 `last_sync.confluence_version` 欄位，然後重新同步。

### Q: 如何只拉取不上傳？

A: 透過 CLI 互動確認：執行 `--sync` 時，針對 CONFLICT 選擇 pull，針對 PUSH 選擇 keep。

## 測試

執行測試套件：

```bash
python3 -m pytest tests/ -v
```

或指定測試檔案：

```bash
python3 -m pytest tests/test_mapping.py tests/test_converter.py tests/test_diff.py -v
```

## 開發

若要貢獻或擴展此專案，請：

1. Fork 本專案
2. 建立 feature 分支
3. 編寫測試與實作
4. 提交 Pull Request

## 授權

MIT License — 詳見 [LICENSE](LICENSE) 檔案。

## 相關資源

- [Confluence REST API 文件](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content/#api-wiki-rest-api-content-id-get)
- [Confluence Storage Format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html)
- [Markdown 規範](https://www.markdownguide.org/)

## 問題與反饋

若發現 Bug 或有功能建議，請開啟 GitHub Issue。
