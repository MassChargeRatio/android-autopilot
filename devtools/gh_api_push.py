#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gh_api_push.py - 当 `github.com` 不可达时，用 REST API 把本地 HEAD 推上去

为什么需要它：本机出口代理能连 `api.github.com`，但 **`github.com` 被挡**
（`CONNECT tunnel failed, response 502`），`git push` 无论换 schannel 还是
openssl 后端都失败。而 git 协议走的正是 `github.com`。
GitHub 的 **Git Data API** 在 `api.github.com` 上，功能等价：
建 blob → 建 tree → 建 commit → 更新 ref。

用法：
    python devtools/gh_api_push.py --repo owner/name --branch main
    python devtools/gh_api_push.py --repo owner/name --dry-run

Token 来源（按优先级）：`--token` > 环境变量 `GITHUB_TOKEN` > Git Credential
Manager（`git-credential-manager get`）。**Token 不会被打印。**

增量：会先读远端 tree，只上传 sha 变化的 blob；未变的直接复用远端 sha。
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://api.github.com"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GCM = (r"C:/Users/Mass/.workbuddy-ai/binaries/PortableGit/versions/1.2.0"
       r"/mingw64/bin/git-credential-manager.exe")


# --------------------------------------------------------------------------
# git 侧
# --------------------------------------------------------------------------
def git(*args, binary=False):
    p = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败："
                           f"{p.stderr.decode('utf-8', 'replace')[:300]}")
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def head_entries():
    """本地 HEAD 的全部 blob：[(mode, sha, path), ...]。"""
    raw = git("ls-tree", "-r", "-z", "HEAD")
    out = []
    for rec in raw.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        mode, _typ, sha = meta.split()
        out.append((mode, sha, path))
    return out


def read_blobs(shas):
    """用一次 `git cat-file --batch` 把所有 blob 内容读出来（省进程开销）。"""
    p = subprocess.run(["git", "-C", ROOT, "cat-file", "--batch"],
                       input=("\n".join(shas) + "\n").encode(),
                       capture_output=True, timeout=600)
    data, pos, out = p.stdout, 0, {}
    for _ in shas:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode()
        if header.endswith(" missing"):
            raise RuntimeError(f"blob 缺失：{header}")
        _sha, _typ, size = header.split()
        size = int(size)
        out[header.split()[0]] = data[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1
    return out


def head_meta():
    fmt = "%H%n%an%n%ae%n%aI%n%s"
    lines = git("log", "-1", f"--format={fmt}").split("\n")
    return {"sha": lines[0], "name": lines[1], "email": lines[2],
            "date": lines[3], "subject": lines[4],
            "message": git("log", "-1", "--format=%B").rstrip("\n")}


# --------------------------------------------------------------------------
# GitHub 侧
# --------------------------------------------------------------------------
class Api:
    def __init__(self, token, dry_run=False):
        self.token = token
        self.dry_run = dry_run
        self.calls = 0

    def __call__(self, path, method="GET", payload=None, ok=(200, 201)):
        if self.dry_run and method != "GET":
            return {"_dry_run": True}
        req = urllib.request.Request(
            API + path, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "gh-api-push",
                     "Content-Type": "application/json"})
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in ok:
                return {"_http": e.code}
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {body[:300]}") from None


def get_token(explicit=None):
    if explicit:
        return explicit
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    if os.path.exists(GCM):
        p = subprocess.run([GCM, "get"],
                           input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        for line in (p.stdout or "").splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    return None


def remote_tree(api, repo, branch):
    """远端分支当前的 tree 映射 {path: sha}；分支不存在返回 (None, None)。"""
    try:
        ref = api(f"/repos/{repo}/git/ref/heads/{branch}")
    except RuntimeError as e:
        if "HTTP 404" in str(e) or "HTTP 409" in str(e):
            return None, None
        raise
    commit_sha = ref["object"]["sha"]
    commit = api(f"/repos/{repo}/git/commits/{commit_sha}")
    tree_sha = commit["tree"]["sha"]
    tree = api(f"/repos/{repo}/git/trees/{tree_sha}?recursive=1")
    return commit_sha, {x["path"]: x["sha"] for x in tree.get("tree", [])
                        if x["type"] == "blob"}


def bootstrap_empty(api, repo, branch):
    """空仓库不接受 Git Data API 建 blob（HTTP 409 "Git Repository is empty"）。

    实测踩过：直接在刚 create 出来的空仓库上建 blob，189 个全部 409。
    必须先用 Contents API 建一个占位文件把第一个提交撑起来，
    之后 Git Data API 才可用。占位文件在随后建 tree 时会被自然丢弃
    （tree 完全按本地 HEAD 生成，不带 base_tree）。
    """
    # Contents API 建/改文件是 **PUT**，不是 POST（POST 会直接 404）
    api(f"/repos/{repo}/contents/.gitkeep", "PUT", {
        "message": "chore: bootstrap repository",
        "content": base64.b64encode(b"# bootstrap\n").decode("ascii"),
        "branch": branch,
    }, ok=(200, 201, 409, 422))


def main():
    ap = argparse.ArgumentParser(description="用 GitHub REST API 推送本地 HEAD")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--token", default=None)
    ap.add_argument("--jobs", type=int, default=10, help="并发上传数")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = get_token(args.token)
    if not token:
        print("FAIL 取不到 token（--token / GITHUB_TOKEN / GCM 都没有）")
        return 2
    api = Api(token, dry_run=args.dry_run)

    entries = head_entries()
    meta = head_meta()
    print(f"本地 HEAD {meta['sha'][:8]}  共 {len(entries)} 个文件")
    print(f"提交者 {meta['name']} <{meta['email']}>  {meta['date']}")
    print(f"目标 {args.repo}@{args.branch}")

    parent, remote = remote_tree(api, args.repo, args.branch)
    if parent:
        print(f"远端已有 {len(remote)} 个 blob（将只上传变化的）")
    elif args.dry_run:
        print("远端分支不存在（首次推送；真实执行时会先 bootstrap）")
    else:
        print("远端分支不存在 —— 先 bootstrap 空仓库")
        bootstrap_empty(api, args.repo, args.branch)
        parent, remote = remote_tree(api, args.repo, args.branch)
        print(f"bootstrap 完成，parent={parent[:8] if parent else None}")

    todo = [e for e in entries if remote is None or remote.get(e[2]) != e[1]]
    print(f"需要上传 {len(todo)} / {len(entries)} 个 blob")

    blobs = read_blobs([e[1] for e in todo]) if todo else {}
    tree_entries, done, failed = [], 0, []

    def upload(ent):
        mode, sha, path = ent
        if api.dry_run:          # dry-run 不真调接口，沿用本地 sha 占位
            return path, sha
        return path, api(f"/repos/{args.repo}/git/blobs", "POST", {
            "content": base64.b64encode(blobs[sha]).decode("ascii"),
            "encoding": "base64"})["sha"]

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futs = {ex.submit(upload, e): e for e in todo}
            for fu in as_completed(futs):
                ent = futs[fu]
                try:
                    path, new_sha = fu.result()
                    tree_entries.append((ent[0], new_sha, path))
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        print(f"  已上传 {done}/{len(todo)}")
                except Exception as e:  # noqa: BLE001
                    failed.append((ent[2], str(e)[:120]))
    if failed:
        print(f"\nFAIL {len(failed)} 个 blob 上传失败：")
        for p, e in failed[:5]:
            print(f"  {p}: {e}")
        return 1

    # 未变化的条目直接沿用远端 sha
    for mode, sha, path in entries:
        if remote is not None and remote.get(path) == sha and \
                not any(t[2] == path for t in tree_entries):
            tree_entries.append((mode, sha, path))

    if args.dry_run:
        print(f"\n[dry-run] 将建 tree（{len(tree_entries)} 项）→ commit → "
              f"{'更新' if parent else '创建'} refs/heads/{args.branch}")
        print(f"[dry-run] 已用 {api.calls} 次 API 调用")
        return 0

    tree = api(f"/repos/{args.repo}/git/trees", "POST", {
        "tree": [{"path": p, "mode": m, "type": "blob", "sha": s}
                 for m, s, p in tree_entries]})
    print(f"tree {tree['sha'][:8]}")

    cpayload = {"message": meta["message"], "tree": tree["sha"],
                "author": {"name": meta["name"], "email": meta["email"],
                           "date": meta["date"]},
                "committer": {"name": meta["name"], "email": meta["email"],
                              "date": meta["date"]}}
    if parent:
        cpayload["parents"] = [parent]
    commit = api(f"/repos/{args.repo}/git/commits", "POST", cpayload)
    print(f"commit {commit['sha'][:8]}")

    if parent:
        api(f"/repos/{args.repo}/git/refs/heads/{args.branch}", "PATCH",
            {"sha": commit["sha"], "force": False})
    else:
        api(f"/repos/{args.repo}/git/refs", "POST",
            {"ref": f"refs/heads/{args.branch}", "sha": commit["sha"]})
    print(f"已推送 -> https://github.com/{args.repo}/tree/{args.branch}"
          f"（{api.calls} 次 API 调用）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
