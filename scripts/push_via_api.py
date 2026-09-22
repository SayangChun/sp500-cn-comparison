# -*- coding: utf-8 -*-
"""
在 git push 被代理阻断时，改用 GitHub REST API（Git Data API）提交本地快照。

流程：读远端 ref -> 取 base tree -> 逐文件建 blob -> 建 tree -> 建 commit -> 更新 ref。
用法：python scripts/push_via_api.py [commit message file]
"""
import base64
import json
import os
import subprocess
import tempfile
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "SayangChun/sp500-cn-comparison"
API = "https://api.github.com"

SKIP_DIRS = {".git", "dist", "node_modules", "__pycache__", ".workbuddy-ai", "venv", ".venv"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def token():
    out = subprocess.run(["git", "credential", "fill"],
                         input=b"protocol=https\nhost=github.com\n\n",
                         capture_output=True).stdout.decode()
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("无法从凭据助手拿到 token")


def api(method, path, tok, payload=None):
    """payload 走临时文件（-d @file）：base64 内容会超出 Windows 命令行长度上限。"""
    tmp = None
    cmd = ["curl", "-s", "--max-time", "90", "-X", method,
           "-H", "Authorization: Bearer " + tok,
           "-H", "Accept: application/vnd.github+json",
           "-H", "User-Agent: sp500-cn-comparison-sync",
           API + path]
    if payload is not None:
        tmp = os.path.join(tempfile.gettempdir(), "gh_payload.json")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        cmd += ["-H", "Content-Type: application/json", "-d", "@" + tmp]
    try:
        r = subprocess.run(cmd, capture_output=True)
        txt = r.stdout.decode("utf-8", "ignore")
        try:
            return json.loads(txt)
        except Exception:                   # noqa: BLE001
            raise SystemExit("API 返回非 JSON: %s" % txt[:300])
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def walk():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            files.append((rel, full))
    return sorted(files)


def main():
    tok = token()
    msg = sys.argv[1] if len(sys.argv) > 1 else "sync from local"

    ref = api("GET", "/repos/%s/git/ref/heads/main" % REPO, tok)
    base_commit = ref["object"]["sha"]
    commit = api("GET", "/repos/%s/git/commits/%s" % (REPO, base_commit), tok)
    base_tree = commit["tree"]["sha"]
    print("base commit:", base_commit[:7])

    tree = []
    for rel, full in walk():
        data = open(full, "rb").read()
        blob = api("POST", "/repos/%s/git/blobs" % REPO, tok,
                   {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        if "sha" not in blob:
            raise SystemExit("建 blob 失败 %s: %s" % (rel, blob))
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("  blob %-32s %6d B" % (rel, len(data)))

    new_tree = api("POST", "/repos/%s/git/trees" % REPO, tok,
                   {"base_tree": base_tree, "tree": tree})
    new_commit = api("POST", "/repos/%s/git/commits" % REPO, tok,
                     {"message": msg, "tree": new_tree["sha"], "parents": [base_commit]})
    if "sha" not in new_commit:
        raise SystemExit("建 commit 失败: %s" % new_commit)
    upd = api("PATCH", "/repos/%s/git/refs/heads/main" % REPO, tok,
              {"sha": new_commit["sha"], "force": False})
    print("new commit:", new_commit["sha"][:7], "| ref updated:",
          "sha" in (upd.get("object") or {}))


if __name__ == "__main__":
    main()
