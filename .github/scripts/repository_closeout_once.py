#!/usr/bin/env python3
"""Archive the reviewed snapshot, then delete only exact, reviewed branch heads.

This one-time tool is for the owner's 2026-11-12 repository-closeout request.
It does not change rulesets, settings, secrets, services, or deployment state.
Default mode is a read-only plan. --execute requires the dedicated Actions ref.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = "Serendipity-min/medical-multi-parameter-monitor"
OPERATION_BRANCH = "codex/repository-cleanup-20261112"
INTEGRATION_BRANCH = "codex/repository-closeout-20261112"
PREFIX = "archive/20261112/"


def git(*args):
    proc = subprocess.run(["git", *args], check=False, text=True, capture_output=True)
    if proc.returncode:
        # checkout uses a masked, short-lived token in git config, never a URL.
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def refs():
    result = {}
    for line in git("ls-remote", "--heads", "--tags", "origin").splitlines():
        sha, ref = line.split("\t", 1)
        if not ref.endswith("^{}"):
            result[ref] = sha
    return result


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-main", required=True)
    parser.add_argument("--expected-integration", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_main), "Invalid main SHA")
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_integration), "Invalid integration SHA")
    origin = git("remote", "get-url", "origin").removesuffix(".git").rstrip("/")
    require(origin == "https://github.com/" + REPOSITORY, "Unexpected origin")
    if args.execute:
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Unexpected Actions repository")
        require(os.environ.get("GITHUB_EVENT_NAME") == "push", "Only the reviewed push event is allowed")
        require(os.environ.get("GITHUB_REF") == "refs/heads/" + OPERATION_BRANCH,
                "Execution requires the one-time operation branch")

    entries = json.loads(Path(args.manifest).read_text())
    require(len(entries) == 41, "Snapshot must contain the 41 reviewed original branches")
    require(len({e["branch"] for e in entries}) == 41, "Duplicate branch in snapshot")
    remote = refs()
    require(remote.get("refs/heads/main") == args.expected_main, "main changed; inspect before retrying")
    deletes, tags = {}, {}
    for entry in entries:
        name, sha = entry["branch"], entry["sha"]
        require(re.fullmatch(r"[0-9a-f]{40}", sha), "Invalid snapshot SHA")
        git("check-ref-format", "refs/heads/" + name)
        tag = PREFIX + name
        require(entry["archive_tag"] == tag, "Unexpected archive mapping")
        git("check-ref-format", "refs/tags/" + tag)
        tags[tag] = sha
        if entry["integrated_in_candidate"]:
            git("merge-base", "--is-ancestor", sha, args.expected_main)
        if name != "main":
            observed = remote.get("refs/heads/" + name)
            # A repeat after an uncertain completion may find a branch already gone.
            require(observed in (None, sha), f"Branch moved: {name}; preserve it")
            if observed is not None:
                deletes[name] = sha
            else:
                require(remote.get("refs/tags/" + tag) == sha,
                        f"Missing branch without verified archive: {name}")

    integrated_head = remote.get("refs/heads/" + INTEGRATION_BRANCH)
    if integrated_head is not None:
        require(integrated_head == args.expected_integration, "Integration branch changed")
        git("merge-base", "--is-ancestor", integrated_head, args.expected_main)
        deletes[INTEGRATION_BRANCH] = integrated_head
    operation_head = remote.get("refs/heads/" + OPERATION_BRANCH)
    if operation_head is not None:
        if args.execute:
            require(operation_head == os.environ.get("GITHUB_SHA"), "Operation branch changed")
        tags[PREFIX + OPERATION_BRANCH] = operation_head
        deletes[OPERATION_BRANCH] = operation_head
    elif args.execute:
        raise RuntimeError("Operation ref no longer exists")
    tags["closeout/20261112"] = args.expected_main
    require("main" not in deletes, "main can never be deleted")
    for tag, sha in tags.items():
        require(remote.get("refs/tags/" + tag) in (None, sha), f"Existing archive differs: {tag}")

    plan = {
        "repository": REPOSITORY,
        "expected_main": args.expected_main,
        "archive_tags": tags,
        "delete_branches": deletes,
        "execution": bool(args.execute),
    }
    print("CLOSEOUT_PLAN " + json.dumps(plan, sort_keys=True), flush=True)
    if not args.execute:
        return

    # Preserve every original tip before deleting any branch. Never rewrite a tag.
    new_tags = []
    for tag, sha in tags.items():
        if "refs/tags/" + tag not in remote:
            git("tag", tag, sha)
            new_tags.append("refs/tags/" + tag)
    if new_tags:
        git("push", "--atomic", "origin", *new_tags)
    archived = refs()
    for tag, sha in tags.items():
        require(archived.get("refs/tags/" + tag) == sha, f"Archive verification failed: {tag}")
    require(archived.get("refs/heads/main") == args.expected_main, "main moved after archiving")
    for name, sha in deletes.items():
        require(archived.get("refs/heads/" + name) == sha, f"Branch moved after archiving: {name}")

    # An atomic push with an explicit lease for each ref preserves concurrent edits.
    # GitHub's branch rules remain authoritative; rejection is a stop, not a bypass.
    if deletes:
        leases = [f"--force-with-lease=refs/heads/{name}:{sha}" for name, sha in deletes.items()]
        git("push", "--atomic", *leases, "origin", *[":refs/heads/" + n for n in deletes])
    final = refs()
    require(final.get("refs/heads/main") == args.expected_main, "Unexpected main state")
    for name in deletes:
        require("refs/heads/" + name not in final, f"Branch still exists: {name}")
    for tag, sha in tags.items():
        require(final.get("refs/tags/" + tag) == sha, f"Archive changed: {tag}")
    remaining = {r.removeprefix("refs/heads/"): s for r, s in final.items()
                 if r.startswith("refs/heads/")}
    receipt = {
        "status": "COMPLETE" if set(remaining) == {"main"} else "PARTIAL_UNKNOWN_BRANCHES_PRESERVED",
        "repository": REPOSITORY,
        "main": args.expected_main,
        "original_branches": len(entries),
        "deleted_this_run": len(deletes),
        "verified_tags": len(tags),
        "remaining_branches": remaining,
    }
    Path("repository-cleanup-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as handle:
            handle.write("## Repository cleanup result\n\n```json\n" + json.dumps(receipt, indent=2) + "\n```\n")
    print("CLOSEOUT_RECEIPT " + json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
