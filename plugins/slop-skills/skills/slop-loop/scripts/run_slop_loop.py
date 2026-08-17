#!/usr/bin/env python3
"""Launch one Codex child session for an autonomous Slop Loop run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


CLEAN_VERDICT = "No open product-impacting findings."
FINGERPRINT_SCRIPT = Path(__file__).with_name("fingerprint_worktree.py").resolve()
RESULT_PREFIX = "SLOP_LOOP_RESULT="
VALID_STATUSES = {"READY_TO_MERGE", "LOCALLY_CLEAN", "BLOCKED", "FAILED"}
PR_NUMBER_RE = re.compile(r"[1-9]\d*")
PR_URL_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/pull/([1-9]\d*)/?")


@dataclass
class HostSettings:
    model: str | None = None
    reasoning_effort: str | None = None
    service_tier: str | None = None
    source: str = "Codex inherited configuration"


@dataclass(frozen=True)
class PrBinding:
    number: int
    url: str
    base_repository: str
    head_repository: str
    head_branch: str
    head_sha: str


@dataclass
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    turns: int = 0

    def add(self, payload: dict[str, Any]) -> None:
        self.input_tokens += integer(payload.get("input_tokens"))
        self.cached_input_tokens += integer(payload.get("cached_input_tokens"))
        self.output_tokens += integer(payload.get("output_tokens"))
        self.reasoning_output_tokens += integer(payload.get("reasoning_output_tokens"))
        self.turns += 1

    @property
    def uncached_input_tokens(self) -> int:
        return max(self.input_tokens - self.cached_input_tokens, 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cache_reuse_rate(self) -> float:
        if self.input_tokens == 0:
            return 0.0
        return self.cached_input_tokens / self.input_tokens


@dataclass
class RunResult:
    child_session_id: str | None
    child_status: str
    exit_status: int
    elapsed_seconds: float
    usage: Usage
    final_message: str
    reported_result: dict[str, Any] | None = None
    verification_errors: tuple[str, ...] = ()
    verification_status: str = "not performed"


def integer(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Slopmeter and Slop Fix in a fresh Codex child session."
    )
    parser.add_argument("--pr", required=True, help="Open PR number or URL")
    parser.add_argument("--repo", required=True, help="Isolated PR worktree")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Do not authorize a commit or push; READY_TO_MERGE is unavailable",
    )
    parser.add_argument("--report", help="Optional Markdown usage-report path")
    parser.add_argument("--codex-bin", default="codex", help=argparse.SUPPRESS)
    parser.add_argument("--codex-home", help=argparse.SUPPRESS)
    parser.add_argument("--host-session-file", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true", help="Print launch data only")
    return parser.parse_args(argv)


def validate_target(pr: str, repo: str) -> tuple[str, Path]:
    target = pr.strip()
    if PR_NUMBER_RE.fullmatch(target) is None and PR_URL_RE.fullmatch(target) is None:
        raise ValueError("--pr must be a positive PR number or canonical GitHub PR URL")
    repo_path = Path(repo).expanduser().resolve()
    if not repo_path.is_dir():
        raise ValueError(f"--repo is not a directory: {repo_path}")
    check = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "true":
        raise ValueError(f"--repo is not a Git worktree: {repo_path}")
    return target, repo_path


def run_command_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise ValueError(f"{command[0]} inspection failed: {message}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"{command[0]} returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{command[0]} returned a non-object JSON value")
    return payload


def repository_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    direct = string_value(value.get("nameWithOwner"))
    if direct:
        return direct
    name = string_value(value.get("name"))
    owner_value = value.get("owner")
    owner = string_value(owner_value.get("login")) if isinstance(owner_value, dict) else None
    return f"{owner}/{name}" if owner and name else None


def resolve_pr_binding(target: str, repo: Path, *, require_push: bool) -> PrBinding:
    git_dir = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-dir"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    common_dir = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if Path(git_dir).resolve() == Path(common_dir).resolve():
        raise ValueError("--repo must be a linked isolated worktree, not the primary worktree")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise ValueError("--repo worktree must be clean before the child starts")

    current_repo = run_command_json(
        ["gh", "repo", "view", "--json", "nameWithOwner"], cwd=repo
    )
    current_name = string_value(current_repo.get("nameWithOwner"))
    fields = (
        "number,url,state,headRefName,headRefOid,headRepository,"
        "headRepositoryOwner,isCrossRepository"
    )
    pr = run_command_json(["gh", "pr", "view", target, "--json", fields], cwd=repo)
    if pr.get("state") != "OPEN":
        raise ValueError("target PR must be open")
    url = string_value(pr.get("url"))
    url_match = PR_URL_RE.fullmatch(url or "")
    if url_match is None:
        raise ValueError("GitHub returned a non-canonical PR URL")
    base_repository = f"{url_match.group(1)}/{url_match.group(2)}"
    if not current_name or current_name.casefold() != base_repository.casefold():
        raise ValueError("--repo does not belong to the target PR base repository")

    owner_value = pr.get("headRepositoryOwner")
    owner = string_value(owner_value.get("login")) if isinstance(owner_value, dict) else None
    head_value = pr.get("headRepository")
    head_repository = repository_name(head_value)
    if head_repository is None and isinstance(head_value, dict):
        name = string_value(head_value.get("name"))
        head_repository = f"{owner}/{name}" if owner and name else None
    head_branch = string_value(pr.get("headRefName"))
    head_sha = string_value(pr.get("headRefOid"))
    number = pr.get("number")
    if (
        not isinstance(number, int)
        or not head_repository
        or not head_branch
        or not head_sha
    ):
        raise ValueError("GitHub returned incomplete PR head metadata")
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if local_sha != head_sha:
        raise ValueError("--repo HEAD does not match the target PR head SHA")
    if require_push:
        permission = run_command_json(
            ["gh", "repo", "view", head_repository, "--json", "viewerPermission"],
            cwd=repo,
        ).get("viewerPermission")
        if permission not in {"ADMIN", "MAINTAIN", "WRITE"}:
            raise ValueError("authenticated GitHub user cannot push to the PR head repository")
    return PrBinding(
        number=number,
        url=url,
        base_repository=base_repository,
        head_repository=head_repository,
        head_branch=head_branch,
        head_sha=head_sha,
    )


def codex_home(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".codex"


def find_host_session(home: Path, thread_id: str | None) -> Path | None:
    if not thread_id:
        return None
    matches: list[Path] = []
    for folder in (home / "sessions", home / "archived_sessions"):
        if folder.is_dir():
            matches.extend(folder.rglob(f"*{thread_id}*.jsonl"))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def normalized_service_tier(value: Any) -> str | None:
    tier = string_value(value)
    if tier == "priority":
        return "fast"
    return tier


def settings_from_session(path: Path, fallback: HostSettings) -> HostSettings:
    settings = HostSettings(
        model=fallback.model,
        reasoning_effort=fallback.reasoning_effort,
        service_tier=fallback.service_tier,
        source=f"host session {path.name}",
    )
    try:
        stream = path.open("r", encoding="utf-8")
    except OSError:
        return fallback
    with stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            candidate: dict[str, Any] | None = None
            if (
                record.get("type") == "event_msg"
                and payload.get("type") == "thread_settings_applied"
            ):
                value = payload.get("thread_settings")
                candidate = value if isinstance(value, dict) else None
            elif record.get("type") == "turn_context":
                candidate = payload
            if candidate is None:
                continue
            settings.model = string_value(candidate.get("model")) or settings.model
            settings.reasoning_effort = (
                string_value(candidate.get("reasoning_effort"))
                or string_value(candidate.get("effort"))
                or settings.reasoning_effort
            )
            if "service_tier" in candidate:
                settings.service_tier = (
                    normalized_service_tier(candidate.get("service_tier")) or "default"
                )
    return settings


def resolve_host_settings(args: argparse.Namespace) -> HostSettings:
    home = codex_home(args.codex_home)
    fallback = HostSettings()
    explicit = (
        Path(args.host_session_file).expanduser().resolve()
        if args.host_session_file
        else None
    )
    session = explicit or find_host_session(home, os.environ.get("CODEX_THREAD_ID"))
    if session is None or not session.is_file():
        return fallback
    return settings_from_session(session, fallback)


def git_common_dir(repo: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = Path(result.stdout.strip())
    return raw.resolve() if raw.is_absolute() else (repo / raw).resolve()


def toml_string(value: str) -> str:
    return json.dumps(value)


def child_prompt(binding: PrBinding, allow_push: bool) -> str:
    publication = (
        "The parent request authorizes normal commits and pushes only to this existing PR head."
        if allow_push
        else "The user supplied --no-push. Do not commit or push, and never return READY_TO_MERGE."
    )
    fingerprint_command = (
        f"python3 {shlex.quote(str(FINGERPRINT_SCRIPT))} --repo ."
    )
    return f"""You are the only child worker for an autonomous PR review-and-repair run.

Target PR: {binding.url}
Base repository: {binding.base_repository}
Exact head destination: {binding.head_repository}:{binding.head_branch}
Starting head SHA: {binding.head_sha}
{publication}

Follow the repository AGENTS.md files and this complete protocol. Do not start another Codex
session or run this launcher script. Explicitly invoke $slop-skills:slopmeter for every review
pass. When that review returns any P-level findings, explicitly invoke
$slop-skills:slop-fix with the complete finding set, verify and repair every in-scope finding,
and review again.

Continue until two consecutive Slopmeter passes on the same product source state return
exactly: {CLEAN_VERDICT}

Before and after every review or repair, run `{fingerprint_command}`. Use its full output as
the only source-state fingerprint. It covers tracked and non-ignored untracked worktree content
and stays stable across a commit-only transition.

The first exact clean pass records its source fingerprint and sets the streak to 1. A later
exact clean pass increments the streak only when its source fingerprint matches; a finding
resets the streak to 0, and a changed clean fingerprint starts a new streak at 1. Require all
repository validations to pass before counting or publishing a clean pass. A failed validation
must stop as BLOCKED with the failed command and evidence.

After the first clean pass, commit and push any loop-owned repair to the exact PR head before
the second pass when publication is authorized. In --no-push mode, leave local changes
uncommitted, do not require remote equality, and return LOCALLY_CLEAN only after two clean local
passes on one fingerprint and successful validations. Never merge, force-push, rewrite history,
change another branch, create another PR, post a review, or deploy. Stop only as BLOCKED when
the same findings and source state repeat after two repair attempts, or an external condition
cannot be changed within this authority.

If a completed Slopmeter invocation returns neither one or more P-level findings nor the exact
clean verdict, it is invalid. Retry that review once on the unchanged fingerprint. If the second
result is also invalid, stop as FAILED with both raw outputs. Never count or repair an invalid
review result.

Before READY_TO_MERGE, prove that the PR is open and not draft, the remote head matches local,
the worktree is clean, no conflict exists, all required checks pass, no required review or
changes-requested state blocks merge, all local validations passed, and both clean passes
covered the same source state.

End your final response with one `SLOP_LOOP_RESULT=` line followed by one compact JSON object.
It must be the last nonempty line. The object must have: status, pr_url, final_head_sha,
source_fingerprint, clean_passes, local_validation, worktree_clean, remote_checks, commits_pushed,
and remote_branch. Each clean_passes entry must have verdict, source_fingerprint, and validation.
Use one status: READY_TO_MERGE, LOCALLY_CLEAN, BLOCKED, or FAILED. Use "passed" for successful
validation and remote checks. Include human-readable pass history, finding outcomes, commits,
checks, and merge proof before the result line.
"""


def build_command(
    codex_binary: str,
    repo: Path,
    settings: HostSettings,
    prompt: str,
) -> list[str]:
    command = [
        codex_binary,
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--color",
        "never",
        "--cd",
        str(repo),
        "--sandbox",
        "workspace-write",
        "--config",
        "sandbox_workspace_write.network_access=true",
    ]
    common_dir = git_common_dir(repo)
    if not common_dir.is_relative_to(repo):
        command.extend(["--add-dir", str(common_dir)])
    if settings.model:
        command.extend(["--model", settings.model])
    if settings.reasoning_effort:
        command.extend(
            ["--config", f"model_reasoning_effort={toml_string(settings.reasoning_effort)}"]
        )
    if settings.service_tier:
        command.extend(
            ["--config", f"service_tier={toml_string(settings.service_tier)}"]
        )
    command.append(prompt)
    return command


def event_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("type") != "turn.completed":
        return None
    value = event.get("usage")
    return value if isinstance(value, dict) else None


def event_agent_message(event: dict[str, Any]) -> str | None:
    if event.get("type") != "item.completed":
        return None
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "agent_message":
        return None
    return string_value(item.get("text"))


def event_progress(event: dict[str, Any]) -> str | None:
    event_type = event.get("type")
    if event_type == "thread.started":
        return f"Child session started: {event.get('thread_id', 'unknown')}"
    if event_type == "turn.completed":
        return "Child turn completed."
    if event_type in {"turn.failed", "error"}:
        message = event.get("message") or event.get("error") or "unknown error"
        return f"Child error: {message}"
    return None


def final_child_result(message: str) -> dict[str, Any] | None:
    lines = message.rstrip().splitlines()
    if not lines:
        return None
    line = lines[-1]
    if not line.startswith(RESULT_PREFIX):
        return None
    try:
        payload = json.loads(line.removeprefix(RESULT_PREFIX))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("status") not in VALID_STATUSES:
        return None
    return payload


def validate_report_path(raw_path: str | None, repo: Path) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path).expanduser().resolve()
    if path == repo or path.is_relative_to(repo):
        raise ValueError("--report must be outside the reviewed worktree")
    return path


def validate_reported_evidence(
    payload: dict[str, Any] | None,
    binding: PrBinding,
    *,
    allow_push: bool,
) -> list[str]:
    if payload is None:
        return ["missing or invalid final SLOP_LOOP_RESULT line"]
    status = payload.get("status")
    errors: list[str] = []
    required_fields = {
        "pr_url",
        "final_head_sha",
        "source_fingerprint",
        "clean_passes",
        "local_validation",
        "worktree_clean",
        "remote_checks",
        "commits_pushed",
        "remote_branch",
    }
    missing = sorted(required_fields - set(payload))
    if missing:
        errors.append(f"child result lacks required fields: {', '.join(missing)}")
    if payload.get("pr_url") != binding.url:
        errors.append("child result PR URL does not match the resolved target")
    if not string_value(payload.get("final_head_sha")):
        errors.append("child result lacks the final head SHA")
    if not string_value(payload.get("source_fingerprint")):
        errors.append("child result lacks the source fingerprint")
    if not isinstance(payload.get("clean_passes"), list):
        errors.append("child result clean_passes must be an array")
    if not isinstance(payload.get("worktree_clean"), bool):
        errors.append("child result worktree_clean must be a boolean")
    if not isinstance(payload.get("commits_pushed"), list):
        errors.append("child result commits_pushed must be an array")
    if payload.get("remote_branch") != f"{binding.head_repository}:{binding.head_branch}":
        errors.append("child result remote branch does not match the PR head")
    if status in {"BLOCKED", "FAILED"}:
        return errors

    expected = "READY_TO_MERGE" if allow_push else "LOCALLY_CLEAN"
    if status != expected:
        errors.append(f"expected child status {expected}, got {status}")
    if payload.get("local_validation") != "passed":
        errors.append("child did not report successful local validation")
    passes = payload.get("clean_passes")
    if not isinstance(passes, list) or len(passes) < 2:
        errors.append("child did not report two clean passes")
    else:
        final_two = passes[-2:]
        fingerprints: list[str] = []
        for item in final_two:
            if not isinstance(item, dict):
                errors.append("clean-pass evidence is not an object")
                continue
            if item.get("verdict") != CLEAN_VERDICT:
                errors.append("clean-pass evidence lacks the exact Slopmeter verdict")
            if item.get("validation") != "passed":
                errors.append("clean-pass evidence lacks successful validation")
            fingerprint = string_value(item.get("source_fingerprint"))
            if fingerprint is None:
                errors.append("clean-pass evidence lacks a source fingerprint")
            else:
                fingerprints.append(fingerprint)
        if len(fingerprints) == 2 and fingerprints[0] != fingerprints[1]:
            errors.append("the final two clean passes used different source fingerprints")
        if fingerprints and payload.get("source_fingerprint") != fingerprints[-1]:
            errors.append("final source fingerprint differs from the clean passes")
    if allow_push:
        if payload.get("worktree_clean") is not True:
            errors.append("child did not report a clean worktree")
        if payload.get("remote_checks") != "passed":
            errors.append("child did not report successful remote checks")
    return errors


def independent_fingerprint_errors(payload: dict[str, Any], repo: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(FINGERPRINT_SCRIPT), "--repo", str(repo)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["independent worktree fingerprint failed"]
    if payload.get("source_fingerprint") != result.stdout.strip():
        return ["final worktree fingerprint differs from the reviewed source state"]
    return []


def required_checks_errors(result: subprocess.CompletedProcess[str]) -> list[str]:
    if result.returncode != 0:
        message = f"{result.stderr}\n{result.stdout}".casefold()
        if result.returncode == 1 and "no required checks reported" in message:
            return []
        return ["required GitHub checks are failed, pending, or unreadable"]
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ["required GitHub checks returned invalid JSON"]
    if not isinstance(payload, list) or any(
        not isinstance(item, dict) or item.get("bucket") not in {"pass", "skipping"}
        for item in payload
    ):
        return ["one or more required GitHub checks did not pass"]
    return []


def verify_remote_ready(binding: PrBinding, repo: Path) -> list[str]:
    errors: list[str] = []
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0 or status.stdout:
        errors.append("independent check found a dirty or unreadable worktree")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    local_sha = head.stdout.strip() if head.returncode == 0 else ""
    try:
        pr = run_command_json(
            [
                "gh",
                "pr",
                "view",
                binding.url,
                "--json",
                "number,url,state,isDraft,headRefName,headRefOid,mergeable,"
                "mergeStateStatus,reviewDecision",
            ],
            cwd=repo,
        )
    except ValueError as error:
        return errors + [str(error)]
    if pr.get("number") != binding.number or pr.get("url") != binding.url:
        errors.append("independent check resolved a different PR")
    if pr.get("state") != "OPEN" or pr.get("isDraft") is not False:
        errors.append("PR is closed or draft")
    if pr.get("headRefName") != binding.head_branch:
        errors.append("remote PR head branch changed during the run")
    remote_sha = string_value(pr.get("headRefOid"))
    if not local_sha or remote_sha != local_sha:
        errors.append("remote PR head does not match local HEAD")
    if pr.get("mergeable") != "MERGEABLE":
        errors.append("GitHub does not report the PR as mergeable")
    if pr.get("mergeStateStatus") != "CLEAN":
        errors.append("GitHub merge state is not clean")
    if pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        errors.append("a review decision still blocks merge")

    checks = subprocess.run(
        [
            "gh",
            "pr",
            "checks",
            binding.url,
            "--required",
            "--json",
            "name,bucket,state",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    errors.extend(required_checks_errors(checks))
    try:
        final_pr = run_command_json(
            ["gh", "pr", "view", binding.url, "--json", "url,headRefOid"],
            cwd=repo,
        )
    except ValueError as error:
        errors.append(str(error))
    else:
        if final_pr.get("url") != binding.url or final_pr.get("headRefOid") != remote_sha:
            errors.append("remote PR head changed while readiness was checked")
    return errors


def run_child(command: list[str]) -> RunResult:
    started = time.monotonic()
    usage = Usage()
    child_session_id: str | None = None
    final_message = ""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    with process.stdout:
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"Child output: {line.rstrip()}", flush=True)
                continue
            if event.get("type") == "thread.started":
                child_session_id = string_value(event.get("thread_id"))
            values = event_usage(event)
            if values is not None:
                usage.add(values)
            message = event_agent_message(event)
            if message is not None:
                final_message = message
            progress = event_progress(event)
            if progress:
                print(progress, flush=True)
    exit_status = process.wait()
    reported_result = final_child_result(final_message)
    child_status = (
        str(reported_result["status"]) if reported_result is not None else "FAILED"
    )
    return RunResult(
        child_session_id=child_session_id,
        child_status=child_status,
        exit_status=exit_status,
        elapsed_seconds=time.monotonic() - started,
        usage=usage,
        final_message=final_message,
        reported_result=reported_result,
    )


def markdown_report(result: RunResult, settings: HostSettings) -> str:
    usage = result.usage
    session_id = result.child_session_id or "not reported"
    return "\n".join(
        [
            "## Slop Loop usage",
            "",
            f"- Child status: {result.child_status}",
            f"- Process exit status: {result.exit_status}",
            f"- Child session: {session_id}",
            f"- Settings source: {settings.source}",
            f"- Model: {settings.model or 'Codex default'}",
            f"- Reasoning effort: {settings.reasoning_effort or 'Codex default'}",
            f"- Service tier: {settings.service_tier or 'Codex default'}",
            f"- Turns: {usage.turns:,}",
            f"- Input tokens: {usage.input_tokens:,}",
            f"- Cached input tokens: {usage.cached_input_tokens:,}",
            f"- Uncached input tokens: {usage.uncached_input_tokens:,}",
            f"- Cache reuse rate: {usage.cache_reuse_rate:.1%}",
            f"- Output tokens: {usage.output_tokens:,}",
            f"- Reasoning output tokens: {usage.reasoning_output_tokens:,}",
            f"- Reported total tokens: {usage.total_tokens:,}",
            f"- Elapsed time: {result.elapsed_seconds:.1f} seconds",
            f"- Independent verification: {result.verification_status}",
            *[f"- Verification error: {error}" for error in result.verification_errors],
        ]
    )


def redacted_launch(command: Iterable[str], prompt: str) -> list[str]:
    return ["<child prompt>" if value == prompt else value for value in command]


def launcher_exit_status(result: RunResult, *, allow_push: bool) -> int:
    if result.exit_status:
        return result.exit_status
    successful = "READY_TO_MERGE" if allow_push else "LOCALLY_CLEAN"
    return 0 if result.child_status == successful and not result.verification_errors else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        pr, repo = validate_target(args.pr, args.repo)
        report_path = validate_report_path(args.report, repo)
        binding = resolve_pr_binding(pr, repo, require_push=not args.no_push)
        settings = resolve_host_settings(args)
        prompt = child_prompt(binding, allow_push=not args.no_push)
        command = build_command(args.codex_bin, repo, settings, prompt)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"Slop Loop launch failed: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "command": redacted_launch(command, prompt),
            "host_settings": asdict(settings),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "publication_authorized": not args.no_push,
            "pr_binding": asdict(binding),
            "repo": str(repo),
            "target_pr": binding.url,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(
        f"Launching Slop Loop with {settings.model or 'Codex default'}, "
        f"{settings.reasoning_effort or 'default reasoning'}, "
        f"{settings.service_tier or 'default service tier'}.",
        flush=True,
    )
    try:
        result = run_child(command)
    except OSError as error:
        print(f"Slop Loop child failed to start: {error}", file=sys.stderr)
        return 2
    verification_errors = validate_reported_evidence(
        result.reported_result,
        binding,
        allow_push=not args.no_push,
    )
    if result.reported_result is not None and result.child_status in {
        "READY_TO_MERGE",
        "LOCALLY_CLEAN",
    }:
        verification_errors.extend(
            independent_fingerprint_errors(result.reported_result, repo)
        )
        local_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        if (
            local_head.returncode != 0
            or result.reported_result.get("final_head_sha") != local_head.stdout.strip()
        ):
            verification_errors.append("child final head SHA does not match local HEAD")
    if result.child_status == "READY_TO_MERGE" and not verification_errors:
        verification_errors.extend(verify_remote_ready(binding, repo))
    if verification_errors:
        result.verification_errors = tuple(verification_errors)
        result.verification_status = "failed"
        result.child_status = "FAILED"
    elif result.child_status in {"READY_TO_MERGE", "LOCALLY_CLEAN"}:
        result.verification_status = "passed"
    else:
        result.verification_status = "not performed"
    if result.final_message:
        print("\n## Slop Loop child result\n")
        print(result.final_message.rstrip())
    report = markdown_report(result, settings)
    print(f"\n{report}")
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report + "\n", encoding="utf-8")
    return launcher_exit_status(result, allow_push=not args.no_push)


if __name__ == "__main__":
    raise SystemExit(main())
