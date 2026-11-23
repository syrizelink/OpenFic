"""Protocol-level Google OAuth/Drive double shared by API and browser tests."""

import json
import re
from email import policy
from email.parser import BytesParser
from urllib.parse import parse_qs

import httpx


class FakeDrive:
    def __init__(self):
        self.files = {}
        self.counter = 0
        self.requests = []

    def add(self, metadata, payload):
        self.counter += 1
        identity = f"drive-{self.counter}"
        self.files[identity] = {
            "id": identity,
            "metadata": metadata,
            "payload": payload,
            "version": 1,
        }
        return identity

    def change(self, identity, content):
        self.files[identity]["payload"]["content"] = content
        self.files[identity]["version"] += 1

    async def __call__(self, request):
        self.requests.append((request.method, str(request.url)))
        path = request.url.path
        if request.url.host == "oauth2.googleapis.com":
            form = parse_qs(request.content.decode())
            if form.get("grant_type") == ["authorization_code"]:
                if form.get("code") != ["test-auth-code"] or not form.get(
                    "code_verifier"
                ):
                    return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(
                200,
                json={
                    "access_token": "test-drive-token",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600,
                },
            )
        if request.headers.get("authorization") != "Bearer test-drive-token":
            return httpx.Response(401, json={"error": "invalid_token"})
        if path == "/drive/v3/files" and request.method == "GET":
            query = request.url.params.get("q", "")
            project = re.search(r"key='openficProjectId' and value='([^']+)'", query)
            files = [
                f
                for f in self.files.values()
                if not project
                or f["metadata"].get("appProperties", {}).get("openficProjectId")
                == project[1]
            ]
            start = int(request.url.params.get("pageToken", "0"))
            page = files[start : start + 2]
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "id": f["id"],
                            **f["metadata"],
                            "modifiedTime": str(f["version"]),
                        }
                        for f in page
                    ],
                    **(
                        {"nextPageToken": str(start + 2)}
                        if start + 2 < len(files)
                        else {}
                    ),
                },
            )
        if path.startswith("/drive/v3/files/") and request.method == "GET":
            entry = self.files.get(path.rsplit("/", 1)[1])
            if entry is None:
                return httpx.Response(404, json={"error": "not_found"})
            return httpx.Response(
                200, json=entry["payload"], headers={"etag": f'"{entry["version"]}"'}
            )
        if path.startswith("/upload/drive/v3/files"):
            mime = BytesParser(policy=policy.default).parsebytes(
                b"Content-Type: "
                + request.headers["content-type"].encode()
                + b"\r\nMIME-Version: 1.0\r\n\r\n"
                + request.content
            )
            parts = list(mime.iter_parts())
            metadata, payload = [json.loads(p.get_payload(decode=True)) for p in parts]
            if request.method == "POST":
                identity = self.add(metadata, payload)
            else:
                identity = path.rsplit("/", 1)[1]
                entry = self.files.get(identity)
                if not entry:
                    return httpx.Response(404, json={"error": "not_found"})
                if (
                    request.headers.get("if-match")
                    and request.headers["if-match"] != f'"{entry["version"]}"'
                ):
                    return httpx.Response(412, json={"error": "precondition_failed"})
                entry.update(
                    metadata=metadata, payload=payload, version=entry["version"] + 1
                )
            return httpx.Response(200, json={"id": identity, "modifiedTime": "now"})
        return httpx.Response(404, json={"error": "unsupported test route"})
