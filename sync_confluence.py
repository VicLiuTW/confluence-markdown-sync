#!/usr/bin/env python3
"""
Confluence 規格同步腳本

用法:
    python3 sync_confluence.py <confluence_url> [--target-dir <dir>]

範例:
    python3 sync_confluence.py "https://your-domain.atlassian.net/wiki/spaces/V/pages/4554782/SPEC"
    python3 sync_confluence.py "https://your-domain.atlassian.net/wiki/spaces/V/pages/4554782" --target-dir "spec/my-docs"

功能:
    1. 從 Confluence URL 抓取頁面內容
    2. 將 HTML 轉換為 Markdown
    3. 比對 spec/ 目錄下的現有檔案
    4. 完全覆蓋並依版號重新命名
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from difflib import SequenceMatcher

try:
    from markdownify import markdownify as md
except ImportError:
    print("錯誤: 請先安裝 markdownify")
    print("  pip3 install markdownify")
    sys.exit(1)


# ── 設定 ──────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
SPEC_DIR = SCRIPT_DIR / "spec"


def load_env():
    """從 .env 讀取設定"""
    env = {}
    if not ENV_FILE.exists():
        print(f"錯誤: 找不到 {ENV_FILE}")
        print("請建立 .env 檔案，包含以下內容:")
        print("  CONFLUENCE_BASE_URL=https://xxx.atlassian.net")
        print("  CONFLUENCE_EMAIL=your@email.com")
        print("  CONFLUENCE_API_TOKEN=your_token")
        sys.exit(1)

    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                val = value.strip()
                if len(val) >= 2 and val[0] in ('"', "'") and val[0] == val[-1]:
                    val = val[1:-1]
                env[key.strip()] = val

    required = ["CONFLUENCE_BASE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN"]
    for key in required:
        if key not in env:
            print(f"錯誤: .env 缺少 {key}")
            sys.exit(1)

    return env


# ── Confluence API ────────────────────────────────────

def make_auth_header(env):
    creds = base64.b64encode(
        f"{env['CONFLUENCE_EMAIL']}:{env['CONFLUENCE_API_TOKEN']}".encode()
    ).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


def extract_page_id(url):
    """從 Confluence URL 提取 page ID"""
    # 格式: .../pages/<pageId>/...
    m = re.search(r"/pages/(\d+)", url)
    if m:
        return m.group(1)

    # 格式: ...?pageId=<pageId>
    m = re.search(r"[?&]pageId=(\d+)", url)
    if m:
        return m.group(1)

    # 短連結格式: /wiki/x/<tinyId> — 需要透過 redirect 解析
    m = re.search(r"/wiki/x/(\S+)", url)
    if m:
        return ("tiny", m.group(1))

    print(f"錯誤: 無法從 URL 提取 page ID: {url}")
    sys.exit(1)


def resolve_tiny_link(env, tiny_id):
    """透過 HTTP redirect 解析短連結取得 page ID"""
    base = env["CONFLUENCE_BASE_URL"]
    url = f"{base}/wiki/x/{tiny_id}"
    headers = make_auth_header(env)

    try:
        req = urllib.request.Request(url, headers=headers)
        # 不自動跟隨 redirect，手動取得 Location
        opener = urllib.request.build_opener(urllib.request.HTTPHandler)
        try:
            resp = opener.open(req)
            final_url = resp.url
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                final_url = e.headers.get("Location", "")
            else:
                raise

        m = re.search(r"/pages/(\d+)", final_url)
        if m:
            return m.group(1)
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass

    print(f"錯誤: 無法解析短連結 /wiki/x/{tiny_id}")
    sys.exit(1)


def fetch_page(env, page_id):
    """抓取頁面標題、版本、HTML 內容"""
    # 處理短連結
    if isinstance(page_id, tuple) and page_id[0] == "tiny":
        page_id = resolve_tiny_link(env, page_id[1])
        print(f"  短連結解析為 page ID: {page_id}")

    base = env["CONFLUENCE_BASE_URL"]
    url = f"{base}/wiki/rest/api/content/{page_id}?expand=body.storage,version,space"
    headers = make_auth_header(env)

    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"錯誤: 找不到頁面 (ID: {page_id})")
        elif e.code == 401:
            print("錯誤: 認證失敗，請檢查 .env 中的 EMAIL 和 API_TOKEN")
        else:
            print(f"錯誤: HTTP {e.code}")
        sys.exit(1)


# ── 圖片處理 ──────────────────────────────────────────

def fetch_attachments(env, page_id):
    """取得頁面附件列表"""
    base = env["CONFLUENCE_BASE_URL"]
    url = f"{base}/wiki/rest/api/content/{page_id}/child/attachment?limit=50"
    headers = make_auth_header(env)
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        return data.get("results", [])
    except urllib.error.HTTPError:
        return []


def download_attachment(env, page_id, filename, target_dir):
    """下載單一附件到指定目錄"""
    base = env["CONFLUENCE_BASE_URL"]
    encoded_name = urllib.request.quote(filename)
    url = f"{base}/wiki/download/attachments/{page_id}/{encoded_name}"
    headers = make_auth_header(env)
    req = urllib.request.Request(url, headers=headers)
    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        print(f"    ⚠ 不安全的檔名: {filename}")
        return False
    target_path = Path(target_dir).resolve() / safe_name
    try:
        resp = urllib.request.urlopen(req)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"    ⚠ 下載失敗 {filename}: {e}")
        return False


def calc_relative_images_path(md_file, images_dir):
    """計算從 md 檔案到 images 目錄的相對路徑"""
    md_path = Path(md_file).resolve()
    img_path = Path(images_dir).resolve()
    try:
        return os.path.relpath(img_path, md_path.parent)
    except ValueError:
        return str(img_path)


def process_images_in_file(env, md_file, images_dir):
    """處理單一 md 檔案中的 [圖片: ...] 佔位符"""
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取 page ID
    m = re.search(r"<!-- sync from: (.+?) -->", content)
    if not m:
        return 0
    sync_url = m.group(1)
    page_id = extract_page_id(sync_url)
    if isinstance(page_id, tuple):
        # 短連結需要解析
        page_id = resolve_tiny_link(env, page_id[1])

    # 找出所有 [圖片: filename] 佔位符
    placeholders = re.findall(r"\[圖片: ([^\]]+)\]", content)
    if not placeholders:
        return 0

    # 取得附件列表
    attachments = fetch_attachments(env, page_id)
    att_names = {a["title"] for a in attachments}

    # 計算相對路徑
    rel_path = calc_relative_images_path(md_file, images_dir)

    downloaded = 0
    for filename in placeholders:
        if filename in att_names:
            img_target = Path(images_dir) / filename
            if not img_target.exists():
                if download_attachment(env, page_id, filename, images_dir):
                    downloaded += 1
                    print(f"    ✓ 下載: {filename}")
                else:
                    continue
            # 替換佔位符
            old_text = f"[圖片: {filename}]"
            new_text = f"![{filename}]({rel_path}/{filename})"
            content = content.replace(old_text, new_text)

    if downloaded > 0 or any(f"![{p}]" in content for p in placeholders):
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(content)

    return downloaded


def batch_download_images(env, target_dir, images_dir):
    """批次處理目錄下所有 md 檔案的圖片"""
    target_path = Path(target_dir).resolve()
    images_path = Path(images_dir).resolve()
    images_path.mkdir(parents=True, exist_ok=True)

    total = 0
    for md_file in sorted(target_path.rglob("*.md")):
        if "archive" in str(md_file) or md_file.name.startswith("_"):
            continue
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        if "[圖片:" not in content:
            continue

        rel = md_file.relative_to(SCRIPT_DIR)
        print(f"\n處理: {rel}")
        count = process_images_in_file(env, md_file, images_dir)
        total += count

    print(f"\n完成！共下載 {total} 張圖片到 {images_path.relative_to(SCRIPT_DIR)}")
    return total


# ── HTML → Markdown ───────────────────────────────────

def html_to_markdown(html_content):
    """將 Confluence HTML 轉換為 Markdown"""
    # 移除 Confluence 特有的 ac: 和 ri: 標籤中的圖片，保留 alt 文字
    html_content = re.sub(
        r'<ac:image[^>]*>.*?</ac:image>',
        lambda m: f"[圖片: {extract_alt(m.group(0))}]",
        html_content,
        flags=re.DOTALL,
    )

    # 移除其他 ac: 標籤但保留內容
    html_content = re.sub(r"</?ac:[^>]*>", "", html_content)
    html_content = re.sub(r"</?ri:[^>]*>", "", html_content)

    # 轉換為 Markdown
    result = md(
        html_content,
        heading_style="atx",
        bullets="-",
        strip=["script", "style"],
    )

    # 清理多餘空行
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def extract_alt(img_tag):
    """從 ac:image 標籤提取 alt 文字"""
    m = re.search(r'ac:alt="([^"]*)"', img_tag)
    if m:
        return m.group(1)
    m = re.search(r'ri:filename="([^"]*)"', img_tag)
    if m:
        return m.group(1)
    return "image"


# ── 版號提取 ──────────────────────────────────────────

def extract_version_from_title(title):
    """從頁面標題提取版號"""
    # 匹配常見版號格式: v1.2, V1.2, v1, V11, v2.1.3
    m = re.search(r"[vV](\d+(?:\.\d+)*)", title)
    if m:
        return f"v{m.group(1)}"
    return None


def extract_version_from_content(html_content):
    """從頁面內容的 metadata 表格提取版號"""
    # 從表格中提取所有 vX.Y 格式的版號（支援「版本紀錄」和「文件版本」表格）
    # 匹配 <td> 中的 v1.0, v1.1 等，帶有 v 前綴
    version_rows = re.findall(
        r'<td[^>]*>\s*(?:<p[^>]*>)?\s*[vV](\d+\.\d+(?:\.\d+)*)\s*(?:</p>)?\s*</td>',
        html_content,
    )
    if version_rows:
        return f"v{version_rows[-1]}"

    # 不帶 v 前綴的版號，後面跟著日期欄位（中間可能隔其他欄位）
    version_rows = re.findall(
        r'<td[^>]*>\s*(?:<p[^>]*>)?\s*(\d+\.\d+(?:\.\d+)*)\s*(?:</p>)?\s*</td>',
        html_content,
    )
    # 過濾掉不像版號的數字（如日期 2025.12.29）
    version_rows = [v for v in version_rows if not re.match(r'20\d{2}\.', v)]
    if version_rows:
        return f"v{version_rows[-1]}"

    # 尋找「文檔版本號」後面的版號
    m = re.search(r"文檔版本號\s*</p>\s*</td>\s*<td>\s*<p>\s*[vV]?(\d+(?:\.\d+)*)", html_content)
    if m:
        return f"v{m.group(1)}"

    # 尋找 version 相關的欄位
    m = re.search(r"(?:版本|version)[號号]?\s*[:：]?\s*[vV]?(\d+(?:\.\d+)*)", html_content, re.IGNORECASE)
    if m:
        return f"v{m.group(1)}"

    return None


# ── 檔案比對 ──────────────────────────────────────────

def normalize_name(name):
    """正規化名稱用於比對：移除版號、日期、底線等"""
    # 移除副檔名
    name = re.sub(r"\.md$", "", name)
    # 移除版號 (v1.2, _v2.1 等)
    name = re.sub(r"[_\-]?[vV]\d+(?:\.\d+)*", "", name)
    # 移除日期 (1229, 20251229, 0113 等)
    name = re.sub(r"[_\-]?\d{4,8}$", "", name)
    # 移除底線和空格統一為空
    name = re.sub(r"[_\-\s]+", " ", name).strip()
    return name.lower()


def find_matching_file(title, target_dir=None):
    """在 spec/ 目錄下找到與標題最匹配的檔案"""
    search_dirs = []
    if target_dir:
        search_dirs.append(Path(target_dir))
    else:
        # 搜尋 spec/ 下所有子目錄（不含 archive）
        for d in SPEC_DIR.rglob("*"):
            if d.is_dir() and "archive" not in str(d) and "_work_log" not in str(d):
                search_dirs.append(d)
        search_dirs.append(SPEC_DIR)

    normalized_title = normalize_name(title)
    candidates = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for f in search_dir.glob("*.md"):
            if f.name.startswith("_") or f.name.startswith("README"):
                continue
            normalized_file = normalize_name(f.name)
            # 計算相似度
            ratio = SequenceMatcher(None, normalized_title, normalized_file).ratio()
            # 也檢查是否有共同的功能編號 (如 F1.1, S6.1.1, US01 等)
            title_codes = set(re.findall(r"[FSUU][S]?\d+(?:\.\d+)*", title, re.IGNORECASE))
            file_codes = set(re.findall(r"[FSUU][S]?\d+(?:\.\d+)*", f.name, re.IGNORECASE))
            code_match = bool(title_codes & file_codes) if title_codes and file_codes else False

            if code_match:
                ratio = max(ratio, 0.8)  # 功能編號匹配，給予高優先級

            if ratio > 0.4:
                candidates.append((f, ratio, code_match))

    # 依相似度排序
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


# ── 主流程 ────────────────────────────────────────────

def run_sync(mapping_file: str) -> None:
    """Execute bidirectional sync based on .sync_mapping.json whitelist."""
    from sync_lib.mapping import load_mapping, save_mapping, resolve_local_file
    from sync_lib.confluence_api import ConfluenceAPI
    from sync_lib.converter import (
        md_to_confluence_html, confluence_html_to_md,
        extract_image_refs, strip_sync_metadata,
    )
    from sync_lib.diff import (
        compute_content_hash, detect_change_type, generate_sync_plan,
        parse_version_table, next_minor_version, append_version_entry,
    )
    import difflib
    from datetime import datetime

    data = load_mapping(mapping_file)
    if not data["pages"]:
        print("錯誤: .sync_mapping.json 中沒有任何 mapping")
        print("請先用 --mapping-add 新增")
        return

    env_file = str(SCRIPT_DIR / ".env")
    api = ConfluenceAPI.from_env(env_file)
    # Read author name for version table entries
    env_data = {}
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_data[k.strip()] = v.strip()
    sync_author = env_data.get("SYNC_AUTHOR", "author")
    meta = data["meta"]
    local_dir = Path(meta["local_dir"])
    if not local_dir.is_absolute():
        local_dir = SCRIPT_DIR / local_dir
    images_dir = local_dir.parent / "images"

    # Phase 1: Detect changes
    changes = []
    for page_id, entry in data["pages"].items():
        local_path = local_dir / entry["local_file"]
        local_exists = local_path.exists()

        local_md = None
        current_hash = None
        if local_exists:
            with open(local_path, "r", encoding="utf-8") as f:
                local_md = f.read()
            local_md = strip_sync_metadata(local_md)
            current_hash = compute_content_hash(local_md)

        is_new = page_id.startswith("new_")
        remote_page = None
        current_version = None
        remote_exists = False
        if not is_new:
            remote_page = api.fetch_page(page_id)
            if remote_page:
                remote_exists = True
                current_version = remote_page["version"]

        action = detect_change_type(
            local_exists=local_exists,
            remote_exists=remote_exists,
            last_sync=entry.get("last_sync"),
            current_hash=current_hash,
            current_version=current_version,
        )

        image_files = []
        if action in ("PUSH", "NEW") and local_md:
            refs = extract_image_refs(local_md)
            image_files = [r["filename"] for r in refs]

        reason_map = {
            "OK": "無變更",
            "PUSH": "本地修改 (hash 不符)",
            "PULL": f"遠端修改 (v{(entry.get('last_sync') or {}).get('confluence_version', '?')} → v{current_version})" if current_version else "遠端修改",
            "CONFLICT": "雙方皆修改",
            "NEW": "尚未同步，將建立 Confluence 頁面" if is_new else "首次同步",
            "DELETED_LOCAL": "本地檔案已刪除",
            "DELETED_REMOTE": "Confluence 頁面已刪除",
        }

        changes.append({
            "action": action,
            "page_id": page_id,
            "local_file": entry["local_file"],
            "reason": reason_map.get(action, action),
            "images": image_files if image_files else None,
            "_local_path": str(local_path),
            "_local_md": local_md,
            "_remote_page": remote_page,
            "_entry": entry,
        })

    # Phase 2: Display sync plan
    plan = generate_sync_plan(changes)
    print(plan)

    actionable = [c for c in changes if c["action"] != "OK"]
    if not actionable:
        print("\n所有檔案都是最新的，無需同步。")
        return

    confirm = input("\n確認執行？ [Y/n] ").strip().lower()
    if confirm and confirm != "y":
        print("已取消")
        return

    # Phase 3: Execute in order: PULL → CONFLICT → NEW → PUSH
    today = datetime.now().strftime("%Y-%m-%d")

    for action_type in ["PULL", "DELETED_LOCAL", "DELETED_REMOTE", "CONFLICT", "NEW", "PUSH"]:
        for change in changes:
            if change["action"] != action_type:
                continue

            page_id = change["page_id"]
            entry = change["_entry"]
            local_path = Path(change["_local_path"])

            if action_type == "PULL":
                _execute_pull(api, data, page_id, entry, local_path, images_dir)
            elif action_type == "PUSH":
                _execute_push(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author)
            elif action_type == "NEW":
                if page_id.startswith("new_"):
                    _execute_new(api, data, page_id, entry, local_path, local_dir, images_dir, meta, today, sync_author)
                else:
                    # Existing Confluence page, first sync — update instead of create
                    _execute_push(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author)
            elif action_type == "CONFLICT":
                _execute_conflict(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author)
            elif action_type == "DELETED_LOCAL":
                _execute_deleted_local(api, data, page_id, entry, local_path, images_dir)
            elif action_type == "DELETED_REMOTE":
                _execute_deleted_remote(data, page_id, entry)

    # Phase 4: Save updated mapping
    save_mapping(data, mapping_file)
    print("\n✓ 同步完成，mapping 已更新")


def _update_sync_snapshot(data: dict, page_id: str, confluence_version: int, local_md: str) -> None:
    from sync_lib.diff import compute_content_hash
    from sync_lib.converter import strip_sync_metadata
    from datetime import datetime
    cleaned = strip_sync_metadata(local_md)
    data["pages"][page_id]["last_sync"] = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "confluence_version": confluence_version,
        "local_content_hash": compute_content_hash(cleaned),
    }


def _execute_pull(api, data, page_id, entry, local_path, images_dir):
    from sync_lib.converter import confluence_html_to_md
    from sync_lib.diff import parse_version_table, next_minor_version
    from datetime import datetime

    print(f"\n  PULL ↓ {entry['local_file']}")
    page = api.fetch_page(page_id)
    new_md = confluence_html_to_md(page["html"])

    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as f:
            old_md = f.read()
        old_vt = parse_version_table(old_md)
        new_vt = parse_version_table(new_md)
        if old_vt["latest_version"] == new_vt["latest_version"] and old_md.strip() != new_md.strip():
            print(f"    ⚠ 內容有變更但版本表未更新")
            suggested_ver = next_minor_version(new_vt["latest_version"])
            today = datetime.now().strftime("%Y-%m-%d")
            print(f"    建議追加: | {suggested_ver} | author | {today} | (請補充變更說明) |")

    _pull_images(api, page_id, page["html"], images_dir)

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(new_md + "\n")
    print(f"    ✓ 已寫入: {entry['local_file']}")

    data["pages"][page_id]["confluence_title"] = page["title"]
    _update_sync_snapshot(data, page_id, page["version"], new_md)


def _execute_push(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author):
    from sync_lib.converter import md_to_confluence_html, confluence_html_to_md
    from sync_lib.diff import parse_version_table, next_minor_version, append_version_entry

    print(f"\n  PUSH ↑ {entry['local_file']}")

    with open(local_path, "r", encoding="utf-8") as f:
        local_md = f.read()

    remote_page = api.fetch_page(page_id)

    vt = parse_version_table(local_md)
    new_ver = next_minor_version(vt["latest_version"])

    print(f"    版本: {vt['latest_version']} → {new_ver}")
    print(f"    請確認變更摘要（直接 Enter 跳過版本表更新，輸入摘要後追加）:")
    summary = input(f"    摘要: ").strip()

    if summary:
        local_md = append_version_entry(local_md, new_ver, today, summary, author=sync_author)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(local_md)
        print(f"    ✓ 版本表已更新: {new_ver}")

    _push_images(api, page_id, local_md, local_dir, images_dir)

    html = md_to_confluence_html(local_md)
    title = _derive_title(entry["local_file"])
    api.update_page(page_id, title, html, remote_page["version"])
    print(f"    ✓ 已推送至 Confluence")

    data["pages"][page_id]["confluence_title"] = title
    _update_sync_snapshot(data, page_id, remote_page["version"] + 1, local_md)


def _execute_new(api, data, page_id, entry, local_path, local_dir, images_dir, meta, today, sync_author):
    from sync_lib.converter import md_to_confluence_html
    from sync_lib.diff import parse_version_table, next_minor_version, append_version_entry

    print(f"\n  NEW    {entry['local_file']}")

    with open(local_path, "r", encoding="utf-8") as f:
        local_md = f.read()

    vt = parse_version_table(local_md)
    new_ver = next_minor_version(vt["latest_version"])
    print(f"    版本: {vt['latest_version'] or '(無)'} → {new_ver}")
    print(f"    請確認變更摘要（直接 Enter 跳過版本表更新）:")
    summary = input(f"    摘要: ").strip()

    if summary:
        local_md = append_version_entry(local_md, new_ver, today, summary, author=sync_author)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(local_md)

    html = md_to_confluence_html(local_md)
    title = _derive_title(entry["local_file"])
    folder_id = meta["confluence_folder_id"]
    result = api.create_page(folder_id, title, html)
    new_page_id = result["id"]
    new_version = result["version"]["number"]

    _push_images(api, new_page_id, local_md, local_dir, images_dir)

    del data["pages"][page_id]
    data["pages"][new_page_id] = {
        "confluence_title": title,
        "local_file": entry["local_file"],
        "last_sync": None,
    }
    _update_sync_snapshot(data, new_page_id, new_version, local_md)
    print(f"    ✓ 已建立 Confluence 頁面 (ID: {new_page_id})")


def _execute_conflict(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author):
    from sync_lib.converter import confluence_html_to_md
    import difflib

    print(f"\n  ⚠ 衝突: {entry['local_file']}")
    last = entry.get("last_sync", {})
    page = api.fetch_page(page_id)
    print(f"    本地: 上次同步後有修改 (hash 不符)")
    print(f"    Confluence: v{last.get('confluence_version', '?')} → v{page['version']}")
    print(f"    上次同步: {last.get('time', '未知')}")

    while True:
        choice = input("    選擇 [L]本地覆蓋遠端 / [R]遠端覆蓋本地 / [D]顯示差異 / [S]跳過: ").strip().upper()
        if choice == "D":
            remote_md = confluence_html_to_md(page["html"])
            with open(local_path, "r", encoding="utf-8") as f:
                local_md = f.read()
            diff = difflib.unified_diff(
                remote_md.splitlines(keepends=True),
                local_md.splitlines(keepends=True),
                fromfile="Confluence",
                tofile="本地",
            )
            for line in diff:
                print(f"    {line}", end="")
            print()
            continue
        if choice == "L":
            _execute_push(api, data, page_id, entry, local_path, local_dir, images_dir, today, sync_author)
            return
        if choice == "R":
            _execute_pull(api, data, page_id, entry, local_path, images_dir)
            return
        if choice == "S":
            print("    已跳過")
            return
        print("    無效選擇，請輸入 L/R/D/S")


def _execute_deleted_local(api, data, page_id, entry, local_path, images_dir):
    print(f"\n  ⚠ 本地已刪除: {entry['local_file']}")
    choice = input("    [R]重新拉取 / [S]跳過: ").strip().upper()
    if choice == "R":
        _execute_pull(api, data, page_id, entry, local_path, images_dir)
    else:
        print("    已跳過")


def _execute_deleted_remote(data, page_id, entry):
    print(f"\n  ⚠ Confluence 已刪除: {entry['local_file']}")
    choice = input("    [X]移除 mapping / [S]跳過: ").strip().upper()
    if choice == "X":
        del data["pages"][page_id]
        print("    ✓ 已移除 mapping")
    else:
        print("    已跳過")


def _derive_title(local_file: str) -> str:
    return local_file.removesuffix(".md")


def _push_images(api, page_id, md_text, local_dir, images_dir):
    from sync_lib.converter import extract_image_refs
    refs = extract_image_refs(md_text)
    if not refs:
        return

    existing_atts = api.list_attachments(page_id)
    existing_by_name = {a["title"]: a["size"] for a in existing_atts}

    for ref in refs:
        filename = ref["filename"]
        img_path = Path(images_dir) / filename
        if not img_path.exists():
            img_path = Path(local_dir) / ref["path"]
        if not img_path.exists():
            print(f"    ⚠ 圖片不存在: {ref['path']}")
            continue

        local_size = img_path.stat().st_size
        if filename in existing_by_name and existing_by_name[filename] == local_size:
            continue

        api.upload_attachment(page_id, str(img_path))
        action = "更新" if filename in existing_by_name else "上傳"
        print(f"    📎 {action}: {filename}")


def _pull_images(api, page_id, html, images_dir):
    filenames = re.findall(r'ri:filename="([^"]*)"', html)
    if not filenames:
        return

    existing_atts = api.list_attachments(page_id)
    att_by_name = {a["title"]: a for a in existing_atts}

    Path(images_dir).mkdir(parents=True, exist_ok=True)

    for filename in filenames:
        if filename not in att_by_name:
            continue

        local_img = Path(images_dir) / filename
        remote_size = att_by_name[filename]["size"]

        if local_img.exists() and local_img.stat().st_size == remote_size:
            continue

        if api.download_attachment(page_id, filename, str(images_dir)):
            action = "更新" if local_img.exists() else "下載"
            print(f"    📎 {action}: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Confluence 規格同步腳本")
    parser.add_argument("url", nargs="?", help="Confluence 頁面 URL")
    parser.add_argument("--target-dir", help="指定目標目錄 (例如 'spec/my-docs')")
    parser.add_argument("--dry-run", action="store_true", help="只顯示差異，不寫入檔案")
    parser.add_argument("--download-images", action="store_true", help="同步時一併下載圖片")
    parser.add_argument("--images-dir", help="圖片存放目錄 (預設: spec/images)")
    parser.add_argument("--batch-images", metavar="DIR", help="批次下載指定目錄下所有 md 檔案的圖片")
    parser.add_argument("--sync", action="store_true", help="雙向同步（根據 .sync_mapping.json 白名單）")
    parser.add_argument("--mapping-add", nargs=2, metavar=("LOCAL_FILE", "PAGE_ID"),
                        help="新增 mapping: 本地檔案 + Confluence page ID")
    parser.add_argument("--mapping-list", action="store_true", help="列出所有 mapping")
    parser.add_argument("--mapping-remove", metavar="PAGE_ID", help="移除 mapping")
    args = parser.parse_args()

    mapping_file = str(SCRIPT_DIR / ".sync_mapping.json")

    # 新增: mapping 管理指令
    if args.mapping_add:
        from sync_lib.mapping import add_entry
        local_file, page_id = args.mapping_add
        add_entry(mapping_file, local_file, page_id)
        print(f"✓ 已新增: {local_file} ↔ {page_id}")
        return

    if args.mapping_list:
        from sync_lib.mapping import list_entries
        entries = list_entries(mapping_file)
        if not entries:
            print("尚無任何 mapping")
            return
        for e in entries:
            synced = f"已同步 (v{e['last_sync']['confluence_version']})" if e["last_sync"] else "未同步"
            print(f"  {e['page_id']:>12}  {e['local_file']:<45s}  {synced}")
        return

    if args.mapping_remove:
        from sync_lib.mapping import remove_entry
        remove_entry(mapping_file, args.mapping_remove)
        print(f"✓ 已移除: {args.mapping_remove}")
        return

    # 新增: 雙向同步
    if args.sync:
        run_sync(mapping_file)
        return

    # 批次圖片模式
    if args.batch_images:
        env = load_env()
        images_dir = args.images_dir or str(SPEC_DIR / "images")
        batch_download_images(env, args.batch_images, images_dir)
        return

    if not args.url:
        parser.error("需要提供 Confluence 頁面 URL（或使用 --sync / --batch-images / --mapping-* 模式）")

    env = load_env()

    # 1. 提取 page ID 並抓取內容
    page_id = extract_page_id(args.url)
    print(f"正在抓取頁面 (ID: {page_id})...")
    page = fetch_page(env, page_id)

    title = page["title"]
    space_key = page["space"]["key"]
    confluence_version = page["version"]["number"]
    html_content = page["body"]["storage"]["value"]

    print(f"  標題: {title}")
    print(f"  Space: {space_key}")
    print(f"  Confluence 版本: {confluence_version}")

    # 2. 提取版號
    version = extract_version_from_title(title)
    if not version:
        version = extract_version_from_content(html_content)
    if not version:
        version = f"v{confluence_version}"
        print(f"  ⚠ 無法從標題/內容提取版號，使用 Confluence 版本號: {version}")
    else:
        print(f"  文檔版號: {version}")

    # 3. 轉換為 Markdown
    markdown_content = html_to_markdown(html_content)

    # 加上 metadata header
    header = f"<!-- sync from: {args.url} -->\n"
    header += f"<!-- confluence version: {confluence_version} -->\n"
    from datetime import datetime as _dt
    header += f"<!-- synced at: {_dt.now().strftime('%Y-%m-%d %H:%M')} -->\n\n"
    full_content = header + markdown_content + "\n"

    print(f"  轉換後大小: {len(full_content)} 字元")

    # 4. 尋找匹配的本地檔案
    target_dir = args.target_dir
    if target_dir and not os.path.isabs(target_dir):
        target_dir = SCRIPT_DIR / target_dir

    candidates = find_matching_file(title, target_dir)

    if not candidates:
        print(f"\n⚠ 找不到與「{title}」匹配的本地檔案")
        print("  請確認是否判斷錯誤，或手動指定 --target-dir")
        print(f"\n  預覽轉換後的前 500 字元:")
        print("  " + "─" * 50)
        for line in full_content[:500].split("\n"):
            print(f"  {line}")
        print("  " + "─" * 50)

        if args.dry_run:
            print("\n[DRY RUN] 不寫入檔案")
            return

        # 詢問是否要手動指定檔案路徑
        answer = input("\n要手動指定輸出檔案路徑嗎？(輸入路徑或按 Enter 取消): ").strip()
        if not answer:
            print("已取消")
            return
        target_file = Path(answer)
        if not target_file.is_absolute():
            target_file = SCRIPT_DIR / target_file
    else:
        print(f"\n找到 {len(candidates)} 個可能匹配的檔案:")
        for i, (f, ratio, code_match) in enumerate(candidates[:5]):
            rel = f.relative_to(SCRIPT_DIR)
            flag = " [功能編號匹配]" if code_match else ""
            print(f"  {i + 1}. {rel}  (相似度: {ratio:.0%}{flag})")

        if args.dry_run:
            target_file = candidates[0][0]
        elif len(candidates) == 1:
            target_file = candidates[0][0]
        else:
            choice = input(f"\n選擇要覆蓋的檔案 (1-{min(5, len(candidates))}，按 Enter 取消): ").strip()
            if not choice:
                print("已取消")
                return
            try:
                idx = int(choice) - 1
                target_file = candidates[idx][0]
            except (ValueError, IndexError):
                print("無效的選擇")
                return

    # 5. 計算新檔名（依版號重命名）
    old_name = target_file.name
    # 移除舊的版號和日期後綴
    base_name = re.sub(r"\.md$", "", old_name)
    base_name = re.sub(r"[_\-]?[vV]\d+(?:\.\d+)*", "", base_name)
    base_name = re.sub(r"[_\-]?\d{4,8}$", "", base_name)
    base_name = base_name.rstrip("_- ")
    new_name = f"{base_name}_{version}.md"
    new_file = target_file.parent / new_name

    print(f"\n  來源: {title} ({version})")
    print(f"  舊檔: {target_file.relative_to(SCRIPT_DIR)}")
    if old_name != new_name:
        print(f"  新檔: {new_file.relative_to(SCRIPT_DIR)}")
    else:
        print(f"  檔名: 不變")

    if args.dry_run:
        print("\n[DRY RUN] 不寫入檔案")
        print(f"\n  預覽轉換後的前 500 字元:")
        print("  " + "─" * 50)
        for line in full_content[:500].split("\n"):
            print(f"  {line}")
        print("  " + "─" * 50)
        return

    # 6. 確認並寫入
    confirm = input("\n確認覆蓋？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    # 如果檔名改變，刪除舊檔
    if target_file != new_file and target_file.exists():
        target_file.unlink()
        print(f"  已刪除舊檔: {old_name}")

    with open(new_file, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"  ✓ 已寫入: {new_file.relative_to(SCRIPT_DIR)}")
    print(f"  ✓ 大小: {len(full_content)} 字元")

    # 7. 下載圖片
    if args.download_images and "[圖片:" in full_content:
        images_dir = args.images_dir or str(new_file.parent.parent / "images")
        if not os.path.isabs(images_dir):
            images_dir = str(SCRIPT_DIR / images_dir)
        print(f"\n  下載圖片到: {Path(images_dir).relative_to(SCRIPT_DIR)}")
        actual_page_id = page_id if not isinstance(page_id, tuple) else resolve_tiny_link(env, page_id[1])
        count = process_images_in_file(env, new_file, images_dir)
        if count:
            print(f"  ✓ 共下載 {count} 張圖片")
        else:
            print(f"  ℹ 無可下載的圖片")


if __name__ == "__main__":
    main()
