#!/usr/bin/env python3
"""Archive the eleven reviewed Dependabot tips before deleting exact branch heads.

One-time closeout for Serendipity-min/medical-multi-parameter-monitor.
The manifest is an array of exactly eleven objects with the fields
branch, head, tag, integrated. Only the reviewed PR #20 entry is integrated.
An optional previous manifest preserves changed old tips under archive/.../previous/.
Default mode makes no remote writes; it may fetch missing reviewed commit objects.
--execute requires the dedicated Actions push/ref and the matching checkout.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPOSITORY = "Serendipity-min/medical-multi-parameter-monitor"
OPERATION_BRANCH = "codex/repository-cleanup-dependencies-20261112"
ARCHIVE_PREFIX = "archive/20261112/"
CLOSEOUT_TAG = "closeout/20261112-dependencies"
PROTECTED_TAG = "closeout/20261112"
PROTECTED_TAG_SHA = "5ea4587fbad66c2f9d3f61990cfa9094ec5f02e7"
INTEGRATED_BRANCH = "dependabot/pip/cloud/backend/websockets-17.4"
RECEIPT_PATH = Path("dependency-cleanup-receipt.json")
EXPECTED_COUNT = 11
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def git(*args):
    proc = subprocess.run(["git", *args], check=False, text=True, capture_output=True)
    if proc.returncode:
        # 凭据由 checkout 的短期 git 配置提供，不写入 URL 或回执。
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def refs():
    result = {}
    for line in git("ls-remote", "--heads", "--tags", "origin").splitlines():
        sha, ref = line.split("\t", 1)
        if not ref.endswith("^{}"):
            result[ref] = sha
    return result


def heads(remote):
    return {ref.removeprefix("refs/heads/"): sha for ref, sha in remote.items()
            if ref.startswith("refs/heads/")}


def read_manifest(path):
    raw = Path(path).read_bytes()
    entries = json.loads(raw)
    require(isinstance(entries, list) and len(entries) == EXPECTED_COUNT,
            "Manifest must contain exactly 11 reviewed dependency branches")
    names, tags = set(), set()
    integrated = 0
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {"branch", "head", "tag", "integrated"},
                "Each entry must contain exactly branch/head/tag/integrated")
        name, sha, tag = entry["branch"], entry["head"], entry["tag"]
        require(isinstance(name, str) and name.startswith("dependabot/"),
                "Only explicit dependabot/ branches are permitted")
        require(isinstance(sha, str) and SHA_PATTERN.fullmatch(sha), "Invalid manifest head SHA")
        require(isinstance(tag, str) and tag == ARCHIVE_PREFIX + name,
                f"Unexpected archive mapping: {name}")
        require(type(entry["integrated"]) is bool, "integrated must be a JSON boolean")
        require(entry["integrated"] == (name == INTEGRATED_BRANCH),
                "The integrated entry must be dependabot/pip/cloud/backend/websockets-17.4")
        require(name not in names and tag not in tags, "Duplicate branch or archive tag")
        git("check-ref-format", "refs/heads/" + name)
        git("check-ref-format", "refs/tags/" + tag)
        names.add(name)
        tags.add(tag)
        integrated += int(entry["integrated"])
    require(integrated == 1, "Only the reviewed PR #20 entry may be marked integrated")
    return entries, hashlib.sha256(raw).hexdigest()


def check_origin():
    expected = "https://github.com/" + REPOSITORY
    for options in (("--all",), ("--push", "--all")):
        urls = git("remote", "get-url", *options, "origin").splitlines()
        require(len(urls) == 1 and urls[0].rstrip("/").removesuffix(".git") == expected,
                "Unexpected origin fetch/push URL")


def ensure_commit(sha):
    probe = subprocess.run(["git", "cat-file", "-e", sha], check=False,
                           text=True, capture_output=True)
    if probe.returncode:
        # 自动合并可能已删除 bot 分支；只取清单中的确切对象，不跟随新分支头。
        git("fetch", "--no-tags", "--no-write-fetch-head", "origin", sha)
    require(git("cat-file", "-t", sha) == "commit", f"Reviewed SHA is not an available commit: {sha}")


def check_snapshot(remote, expected_main, entries, operation_head, protected_tag):
    require(remote.get("refs/heads/main") == expected_main, "main changed; inspect before retrying")
    require(protected_tag == PROTECTED_TAG_SHA,
            "Original closeout/20261112 must exist at its reviewed 5ea4587 commit")
    require(remote.get("refs/tags/" + PROTECTED_TAG) == protected_tag,
            "The original closeout/20261112 tag changed; do not rewrite it")
    for entry in entries:
        observed = remote.get("refs/heads/" + entry["branch"])
        require(observed in (None, entry["head"]), f"Branch moved: {entry['branch']}; preserve it")
    require(remote.get("refs/heads/" + OPERATION_BRANCH) == operation_head,
            "Operation branch changed or disappeared")


def push_updates(output):
    """Read only successful per-ref porcelain statuses, never infer deletion counts."""
    updates = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and fields[0] in {" ", "+", "-", "*", "=", "!"}:
            destination = fields[1].split(":", 1)[-1]
            updates[destination] = fields[0]
    return updates


def run(args, receipt):
    require(SHA_PATTERN.fullmatch(args.expected_main), "Invalid expected main SHA")
    entries, digest = read_manifest(args.manifest)
    receipt.update(expected_main=args.expected_main, manifest_sha256=digest,
                   reviewed_dependency_branches=len(entries))
    previous = []
    if args.previous_manifest:
        previous, previous_digest = read_manifest(args.previous_manifest)
        require({entry["branch"] for entry in previous} == {entry["branch"] for entry in entries},
                "Previous manifest must contain the same 11 dependency branch names")
        receipt["previous_manifest_sha256"] = previous_digest
    check_origin()
    if args.execute:
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Unexpected Actions repository")
        require(os.environ.get("GITHUB_EVENT_NAME") == "push", "Only the reviewed push event is allowed")
        require(os.environ.get("GITHUB_REF") == "refs/heads/" + OPERATION_BRANCH,
                "Execution requires the dedicated operation branch")
        action_sha = os.environ.get("GITHUB_SHA", "")
        require(SHA_PATTERN.fullmatch(action_sha), "Invalid Actions SHA")
        require(git("rev-parse", "HEAD") == action_sha, "Checkout differs from the Actions SHA")
    require(git("rev-parse", "--is-shallow-repository") == "false",
            "Complete ancestry is required; use checkout fetch-depth: 0")

    remote = refs()
    protected_tag = remote.get("refs/tags/" + PROTECTED_TAG)
    operation_head = remote.get("refs/heads/" + OPERATION_BRANCH)
    if args.execute:
        require(operation_head == action_sha, "Operation branch changed or no longer exists")
    check_snapshot(remote, args.expected_main, entries, operation_head, protected_tag)
    ensure_commit(args.expected_main)
    tags = {entry["tag"]: entry["head"] for entry in entries}
    for entry in entries:
        ensure_commit(entry["head"])
        if entry["integrated"]:
            # 合并标志不是证明；确切 tip 必须能从本次 expected-main 追溯。
            git("merge-base", "--is-ancestor", entry["head"], args.expected_main)
    current_heads = {entry["branch"]: entry["head"] for entry in entries}
    previous_archives = {}
    for entry in previous:
        if entry["head"] == current_heads[entry["branch"]]:
            continue
        ensure_commit(entry["head"])
        if entry["integrated"]:
            git("merge-base", "--is-ancestor", entry["head"], args.expected_main)
        tag = ARCHIVE_PREFIX + "previous/" + entry["branch"]
        tags[tag] = entry["head"]
        previous_archives[entry["branch"]] = {
            "head": entry["head"], "tag": tag, "current_head": current_heads[entry["branch"]],
        }
    if operation_head is not None:
        ensure_commit(operation_head)
        tags[ARCHIVE_PREFIX + OPERATION_BRANCH] = operation_head
    tags[CLOSEOUT_TAG] = args.expected_main
    require(PROTECTED_TAG not in tags, "The first closeout tag must never be written")
    for tag, sha in tags.items():
        git("check-ref-format", "refs/tags/" + tag)
        require(remote.get("refs/tags/" + tag) in (None, sha), f"Existing archive differs: {tag}")

    absent_at_start = [entry["branch"] for entry in entries
                       if "refs/heads/" + entry["branch"] not in remote]
    known = {entry["branch"] for entry in entries} | {"main", OPERATION_BRANCH}
    planned_deletes = {entry["branch"]: entry["head"] for entry in entries
                       if entry["branch"] not in absent_at_start}
    if operation_head is not None:
        planned_deletes[OPERATION_BRANCH] = operation_head
    receipt.update(
        protected_original_closeout=protected_tag,
        archive_tags=tags,
        previous_tip_archives=previous_archives,
        already_absent_at_start=absent_at_start,
        planned_delete_branches=planned_deletes,
        unknown_branches_at_start={name: sha for name, sha in heads(remote).items() if name not in known},
    )
    print("DEPENDENCY_CLEANUP_PLAN " + json.dumps(receipt, sort_keys=True), flush=True)
    if not args.execute:
        receipt.update(status="PLAN_ONLY", phase="plan", remaining_branches=heads(remote))
        return

    # 不创建本地标签，不强写既有标签。空值 lease 只允许创建先前不存在的 tag。
    new_tags = {tag: sha for tag, sha in tags.items() if "refs/tags/" + tag not in remote}
    if new_tags:
        receipt.update(phase="archive_push", archive_push_outcome="UNKNOWN_UNTIL_READBACK")
        leases = ["--force-with-lease=refs/tags/" + tag + ":" for tag in new_tags]
        git("push", "--porcelain", "--atomic", *leases, "origin",
            *[sha + ":refs/tags/" + tag for tag, sha in new_tags.items()])
    archived = refs()
    for tag, sha in tags.items():
        require(archived.get("refs/tags/" + tag) == sha, f"Archive verification failed: {tag}")
    receipt.update(phase="archive_verified", archive_push_outcome="VERIFIED",
                   verified_archive_tags=len(tags))
    check_snapshot(archived, args.expected_main, entries, operation_head, protected_tag)

    # 若 bot 已自动删除分支，则不把它计为脚本删除；同名分支复建则停止复核。
    require(all("refs/heads/" + name not in archived for name in absent_at_start),
            "A previously absent dependency branch was recreated; inspect before retrying")
    deletes = {name: sha for name, sha in planned_deletes.items()
               if "refs/heads/" + name in archived}
    absent_before_delete = [entry["branch"] for entry in entries
                           if "refs/heads/" + entry["branch"] not in archived]
    receipt.update(absent_before_delete=absent_before_delete,
                   disappeared_before_delete=sorted(set(absent_before_delete) - set(absent_at_start)),
                   attempted_delete_branches=deletes)
    require("main" not in deletes, "main can never be deleted")
    require(set(deletes) <= ({entry["branch"] for entry in entries} | {OPERATION_BRANCH}),
            "Deletion set exceeded the exact reviewed manifest")

    # 保护规则拒绝即停止；不降级为逐条删除、无 lease 强推或修改仓库规则。
    receipt.update(phase="delete_push", deleted_this_run=None, deletion_push_outcome="UNKNOWN_UNTIL_READBACK")
    leases = [f"--force-with-lease=refs/heads/{name}:{sha}" for name, sha in deletes.items()]
    output = git("push", "--porcelain", "--atomic", *leases, "origin",
                 *[":refs/heads/" + name for name in deletes])
    statuses = push_updates(output)
    expected_refs = {"refs/heads/" + name for name in deletes}
    require(set(statuses) == expected_refs and all(flag in {"-", "="} for flag in statuses.values()),
            "Unexpected push status; verify remote state before retrying")
    deleted = sorted(ref.removeprefix("refs/heads/") for ref, flag in statuses.items() if flag == "-")
    receipt.update(deleted_this_run=len(deleted), deleted_branches=deleted,
                   deleted_dependencies_this_run=sum(name != OPERATION_BRANCH for name in deleted),
                   deleted_operation_branch=OPERATION_BRANCH in deleted,
                   deletion_push_outcome="PUSH_ACKNOWLEDGED", phase="final_readback")
    final = refs()
    receipt["remaining_branches"] = heads(final)
    require(final.get("refs/heads/main") == args.expected_main, "main changed during cleanup")
    require(final.get("refs/tags/" + PROTECTED_TAG) == protected_tag, "Original closeout tag changed")
    for tag, sha in tags.items():
        require(final.get("refs/tags/" + tag) == sha, f"Archive changed: {tag}")
    for name in known - {"main"}:
        require("refs/heads/" + name not in final, f"Reviewed branch still exists or was recreated: {name}")
    remaining_unknown = {name: sha for name, sha in heads(final).items() if name != "main"}
    receipt.update(
        status="PARTIAL_UNKNOWN_BRANCHES_PRESERVED" if remaining_unknown else "COMPLETE",
        phase="complete",
        deletion_push_outcome="VERIFIED",
        preserved_unknown_branches=remaining_unknown,
        protected_original_closeout_unchanged=True,
    )


def write_receipt(receipt):
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    RECEIPT_PATH.write_text(payload, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("## Dependency cleanup result\n\n```json\n" + payload + "```\n")
    print("DEPENDENCY_CLEANUP_RECEIPT " + json.dumps(receipt, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--previous-manifest")
    parser.add_argument("--expected-main", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    receipt = {"status": "PREFLIGHT", "phase": "preflight", "repository": REPOSITORY,
               "execution": bool(args.execute), "deleted_this_run": 0}
    exit_code = 0
    try:
        run(args, receipt)
    except (RuntimeError, OSError, ValueError) as exc:
        # 推送/网络失败不自动重试；若已开始写事务，保留 UNKNOWN，不假报零删除。
        receipt.update(status="STOPPED", error=str(exc))
        exit_code = 1
    write_receipt(receipt)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
