#!/usr/bin/env python3
"""Create, refresh, or migrate the managed Slop Brief in a PR description."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


START_MARKER = "<!-- slop-brief:start -->"
END_MARKER = "<!-- slop-brief:end -->"
LEGACY_START_MARKER = "<!-- change-brief:start -->"
LEGACY_END_MARKER = "<!-- change-brief:end -->"
PR_URL_RE = re.compile(r"https://github\.com/(?P<repo>[^/]+/[^/]+)/pull/(?P<number>\d+)")
SUMMARY_PREFIX = "**What this PR changes:**"
REQUIRED_HEADINGS = ("## Dictionary", "## Changes in logical order")


class PublishError(RuntimeError):
    pass


def run_gh(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown gh failure"
        raise PublishError(detail)
    return result.stdout


def read_brief(path: str) -> str:
    value = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = value.strip()
    if not value:
        raise PublishError("the Slop Brief is empty")
    marker = next(
        (
            candidate
            for candidate in (
                START_MARKER,
                END_MARKER,
                LEGACY_START_MARKER,
                LEGACY_END_MARKER,
            )
            if candidate in value
        ),
        None,
    )
    if marker:
        raise PublishError("the brief file must not contain managed-section markers")

    summary_lines = [
        line for line in value.splitlines() if line.startswith(SUMMARY_PREFIX)
    ]
    if (
        len(summary_lines) != 1
        or not summary_lines[0][len(SUMMARY_PREFIX) :].strip()
        or not value.startswith(SUMMARY_PREFIX)
    ):
        raise PublishError(
            "the brief must start with one non-empty "
            "'**What this PR changes:**' sentence"
        )

    positions = [value.find(heading) for heading in REQUIRED_HEADINGS]
    if -1 in positions or positions != sorted(positions):
        raise PublishError(
            "the brief must contain '## Dictionary' followed by "
            "'## Changes in logical order'"
        )
    return value


def managed_section(brief: str) -> str:
    return f"{START_MARKER}\n## Slop Brief\n\n{brief}\n{END_MARKER}"


def marker_range(
    body: str,
    start_marker: str,
    end_marker: str,
    label: str,
) -> tuple[int, int] | None:
    start_count = body.count(start_marker)
    end_count = body.count(end_marker)
    if start_count != end_count:
        raise PublishError(f"the PR description contains an incomplete {label} marker pair")
    if start_count > 1:
        raise PublishError(f"the PR description contains duplicate {label} sections")
    if start_count == 0:
        return None

    start = body.find(start_marker)
    end = body.find(end_marker)
    if end < start:
        raise PublishError(f"the {label} markers are out of order")
    return start, end + len(end_marker)


def merge_description(body: str, section: str) -> tuple[str, str]:
    current = marker_range(body, START_MARKER, END_MARKER, "Slop Brief")
    legacy = marker_range(
        body,
        LEGACY_START_MARKER,
        LEGACY_END_MARKER,
        "legacy Change Brief",
    )
    if current and legacy:
        raise PublishError("the PR description contains both Slop Brief and legacy Change Brief sections")

    marker = current or legacy
    if marker:
        start, end = marker
        updated = body[:start] + section + body[end:]
        if updated == body:
            return updated, "unchanged"
        return updated, "migrated" if legacy else "updated"

    prefix = body.rstrip()
    updated = f"{prefix}\n\n{section}" if prefix else section
    return updated, "created"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", required=True, help="Pull request number or URL")
    parser.add_argument("--brief-file", required=True, help="Markdown file, or - for stdin")
    parser.add_argument("--dry-run", action="store_true", help="Print the merged description without editing GitHub")
    parser.add_argument("--allow-closed", action="store_true", help="Permit explicit updates to closed or merged PRs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        brief = read_brief(args.brief_file)
        metadata = json.loads(run_gh("pr", "view", args.pr, "--json", "number,state,url,body"))
        state = metadata["state"]
        if state != "OPEN" and not args.allow_closed:
            raise PublishError(f"PR is {state.lower()}; refusing to update it without --allow-closed")

        url = metadata["url"]
        match = PR_URL_RE.fullmatch(url)
        if not match:
            raise PublishError(f"could not derive the repository from PR URL: {url}")

        description, action = merge_description(
            metadata.get("body") or "",
            managed_section(brief),
        )
        if args.dry_run:
            print(description)
        elif action != "unchanged":
            payload = json.dumps({"body": description})
            run_gh(
                "api",
                "--method",
                "PATCH",
                f"repos/{match.group('repo')}/pulls/{metadata['number']}",
                "--input",
                "-",
                stdin=payload,
            )

        print(
            json.dumps({"action": action, "pr": metadata["number"], "url": url}),
            file=sys.stderr if args.dry_run else sys.stdout,
        )
        return 0
    except (OSError, ValueError, KeyError, PublishError) as error:
        print(f"slop-brief publish failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
