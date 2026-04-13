"""Thin Confluence REST API v1 wrapper."""

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath


def _safe_filename(filename: str) -> str:
    """Strip path components from filename to prevent path traversal."""
    name = PurePosixPath(filename).name
    name = name.split("\\")[-1]
    if not name or name in (".", ".."):
        raise ValueError(f"Invalid attachment filename: {filename!r}")
    return name


class ConfluenceAPI:
    """Confluence REST API v1 client using Basic Auth."""

    REQUEST_TIMEOUT = 30  # seconds

    def __init__(self, base_url: str, email: str, api_token: str):
        if not base_url.startswith("https://"):
            raise ValueError("CONFLUENCE_BASE_URL must use HTTPS")
        self.base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._auth_header = f"Basic {creds}"

    @classmethod
    def from_env(cls, env_file: str) -> "ConfluenceAPI":
        """Parse .env file (KEY=VALUE lines) and create instance."""
        env = {}
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    val = value.strip()
                    if len(val) >= 2 and val[0] in ('"', "'") and val[0] == val[-1]:
                        val = val[1:-1]
                    env[key.strip()] = val
        return cls(
            base_url=env["CONFLUENCE_BASE_URL"],
            email=env["CONFLUENCE_EMAIL"],
            api_token=env["CONFLUENCE_API_TOKEN"],
        )

    def _request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        headers: dict | None = None,
    ) -> dict | bytes | None:
        """Internal HTTP helper. Returns parsed JSON, raw bytes, or None on 404."""
        url = self.base_url + path
        req_headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as resp:
                content_type = resp.headers.get("Content-Type", "")
                body = resp.read()
                if not body:
                    return None
                if "application/json" in content_type:
                    return json.loads(body)
                return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def fetch_page(self, page_id: str) -> dict | None:
        """Fetch page content. Returns {id, title, version, html} or None on 404."""
        path = f"/wiki/rest/api/content/{page_id}?expand=body.storage,version"
        result = self._request("GET", path)
        if result is None:
            return None
        return {
            "id": result["id"],
            "title": result["title"],
            "version": result["version"]["number"],
            "html": result["body"]["storage"]["value"],
        }

    def update_page(
        self,
        page_id: str,
        title: str,
        html: str,
        current_version: int,
    ) -> dict:
        """Update existing page with new version = current_version + 1."""
        path = f"/wiki/rest/api/content/{page_id}"
        payload = {
            "version": {"number": current_version + 1},
            "title": title,
            "type": "page",
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage",
                }
            },
        }
        data = json.dumps(payload).encode("utf-8")
        return self._request(
            "PUT",
            path,
            data=data,
            headers={"Content-Type": "application/json"},
        )

    def create_page(self, folder_id: str, title: str, html: str, space_key: str = "EXAMPLE") -> dict:
        """Create a new child page under folder_id."""
        path = "/wiki/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": folder_id}],
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage",
                }
            },
        }
        data = json.dumps(payload).encode("utf-8")
        return self._request(
            "POST",
            path,
            data=data,
            headers={"Content-Type": "application/json"},
        )

    def list_attachments(self, page_id: str) -> list[dict]:
        """List page attachments. Returns list of {title, size, download_url, id}."""
        path = f"/wiki/rest/api/content/{page_id}/child/attachment?limit=100"
        result = self._request("GET", path)
        if not result:
            return []
        attachments = []
        for item in result.get("results", []):
            attachments.append({
                "id": item["id"],
                "title": item["title"],
                "size": item.get("extensions", {}).get("fileSize", 0),
                "download_url": item.get("_links", {}).get("download", ""),
            })
        return attachments

    def upload_attachment(self, page_id: str, filepath: str) -> dict:
        """Upload or update an attachment. Uses multipart form data."""
        file_path = Path(filepath)
        filename = file_path.name
        file_data = file_path.read_bytes()

        # Check if attachment already exists
        existing = self.list_attachments(page_id)
        existing_map = {att["title"]: att["id"] for att in existing}

        boundary = "----ConfluenceAPIBoundary"
        body_parts = [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{re.sub(r"""["\\\r\n]""", "_", filename)}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n",
            b"\r\n",
            file_data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        body = b"".join(body_parts)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Atlassian-Token": "nocheck",
        }

        if filename in existing_map:
            att_id = existing_map[filename]
            path = f"/wiki/rest/api/content/{page_id}/child/attachment/{att_id}/data"
        else:
            path = f"/wiki/rest/api/content/{page_id}/child/attachment"

        return self._request("POST", path, data=body, headers=headers)

    def download_attachment(
        self, page_id: str, filename: str, target_dir: str
    ) -> bool:
        """Download attachment by name. Returns True on success, False on failure."""
        encoded_name = urllib.parse.quote(filename)
        path = f"/wiki/download/attachments/{page_id}/{encoded_name}"
        result = self._request("GET", path)
        if result is None:
            return False
        sanitized = _safe_filename(filename)
        target_path = Path(target_dir).resolve() / sanitized
        if not str(target_path).startswith(str(Path(target_dir).resolve())):
            raise ValueError(f"Path traversal detected: {filename!r}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(result if isinstance(result, bytes) else result.encode())
        return True
