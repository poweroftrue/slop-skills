#!/usr/bin/env python3
"""Print a commit-independent SHA-256 fingerprint of a Git worktree's source state."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path


def tracked_and_untracked_paths(repo: Path) -> list[bytes]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return sorted(set(path for path in result.stdout.split(b"\0") if path))


def gitlinks(repo: Path) -> dict[bytes, bytes]:
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    links: dict[bytes, bytes] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry or b"\t" not in entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        fields = metadata.split()
        if len(fields) == 3 and fields[0] == b"160000" and fields[2] == b"0":
            links[path] = fields[1]
    return links


def add_field(digest: object, label: bytes, value: bytes) -> None:
    digest.update(len(label).to_bytes(8, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def fingerprint(repo: Path) -> str:
    digest = hashlib.sha256()
    submodules = gitlinks(repo)
    for raw_path in tracked_and_untracked_paths(repo):
        path = repo / os.fsdecode(raw_path)
        add_field(digest, b"path", raw_path)
        if raw_path in submodules:
            add_field(digest, b"kind", b"submodule")
            if not (path / ".git").exists():
                add_field(digest, b"uninitialized-gitlink", submodules[raw_path])
                continue
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                check=True,
                capture_output=True,
            ).stdout.strip()
            add_field(digest, b"submodule-head", head)
            add_field(digest, b"submodule-content", fingerprint(path).encode("ascii"))
            continue
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            add_field(digest, b"kind", b"deleted")
            continue
        executable = b"1" if metadata.st_mode & 0o111 else b"0"
        add_field(digest, b"executable", executable)
        if stat.S_ISLNK(metadata.st_mode):
            add_field(digest, b"kind", b"symlink")
            add_field(digest, b"target", os.fsencode(os.readlink(path)))
        elif stat.S_ISREG(metadata.st_mode):
            add_field(digest, b"kind", b"file")
            add_field(digest, b"size", str(metadata.st_size).encode("ascii"))
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif stat.S_ISDIR(metadata.st_mode):
            add_field(digest, b"kind", b"directory")
        else:
            add_field(digest, b"kind", b"special")
    return f"sha256:{digest.hexdigest()}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Git worktree to fingerprint")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2
    try:
        print(fingerprint(repo))
    except (OSError, subprocess.SubprocessError) as error:
        print(f"fingerprint failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
