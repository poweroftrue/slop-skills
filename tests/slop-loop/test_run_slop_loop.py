from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT
    / "plugins/slop-skills/skills/slop-loop/scripts/run_slop_loop.py"
)
FINGERPRINT_PATH = SCRIPT_PATH.with_name("fingerprint_worktree.py")
SPEC = importlib.util.spec_from_file_location("run_slop_loop", SCRIPT_PATH)
assert SPEC and SPEC.loader
LOOP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LOOP
SPEC.loader.exec_module(LOOP)
FINGERPRINT_SPEC = importlib.util.spec_from_file_location(
    "fingerprint_worktree", FINGERPRINT_PATH
)
assert FINGERPRINT_SPEC and FINGERPRINT_SPEC.loader
FINGERPRINT = importlib.util.module_from_spec(FINGERPRINT_SPEC)
sys.modules[FINGERPRINT_SPEC.name] = FINGERPRINT
FINGERPRINT_SPEC.loader.exec_module(FINGERPRINT)


class SlopLoopLauncherTests(unittest.TestCase):
    def binding(self) -> object:
        return LOOP.PrBinding(
            number=132,
            url="https://github.com/example/project/pull/132",
            base_repository="example/project",
            head_repository="example/project",
            head_branch="fix-branch",
            head_sha="a" * 40,
        )

    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def make_linked_worktree(self, root: Path) -> tuple[Path, Path, str]:
        repo = self.make_repo(root)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "Base"], check=True)
        linked = root / "linked"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-qb", "pr-test", str(linked)],
            check=True,
        )
        sha = subprocess.run(
            ["git", "-C", str(linked), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return repo, linked, sha

    def write_session(self, root: Path, records: list[dict]) -> Path:
        path = root / "session.jsonl"
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return path

    def test_session_settings_override_config_and_priority_maps_to_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = self.write_session(
                root,
                [
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "thread_settings_applied",
                            "thread_settings": {
                                "model": "gpt-test",
                                "reasoning_effort": "xhigh",
                                "service_tier": "priority",
                            },
                        },
                    }
                ],
            )
            settings = LOOP.settings_from_session(
                session,
                LOOP.HostSettings(model="fallback", source="fallback"),
            )
        self.assertEqual(settings.model, "gpt-test")
        self.assertEqual(settings.reasoning_effort, "xhigh")
        self.assertEqual(settings.service_tier, "fast")
        self.assertIn("session.jsonl", settings.source)

    def test_turn_context_is_a_supported_session_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = self.write_session(
                root,
                [
                    {
                        "type": "turn_context",
                        "payload": {"model": "gpt-turn", "effort": "high"},
                    }
                ],
            )
            settings = LOOP.settings_from_session(session, LOOP.HostSettings())
        self.assertEqual(settings.model, "gpt-turn")
        self.assertEqual(settings.reasoning_effort, "high")

    def test_explicit_standard_session_tier_overrides_fast_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = self.write_session(
                root,
                [
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "thread_settings_applied",
                            "thread_settings": {"service_tier": None},
                        },
                    }
                ],
            )
            settings = LOOP.settings_from_session(
                session,
                LOOP.HostSettings(service_tier="fast", source="fallback"),
            )
        self.assertEqual(settings.service_tier, "default")

    def test_missing_session_omits_overrides_instead_of_parsing_top_level_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config.toml").write_text(
                'model = "wrong-without-profile-precedence"\n', encoding="utf-8"
            )
            args = LOOP.parse_args(
                ["--pr", "132", "--repo", temporary, "--codex-home", temporary]
            )
            with mock.patch.dict(LOOP.os.environ, {"CODEX_THREAD_ID": ""}):
                settings = LOOP.resolve_host_settings(args)
        self.assertIsNone(settings.model)
        self.assertEqual(settings.source, "Codex inherited configuration")

    def test_command_uses_matched_settings_and_a_writable_network_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = self.make_repo(Path(temporary))
            settings = LOOP.HostSettings("gpt-test", "xhigh", "fast", "test")
            command = LOOP.build_command("codex-test", repo, settings, "prompt")
        self.assertEqual(command[0:4], ["codex-test", "--ask-for-approval", "never", "exec"])
        self.assertIn("workspace-write", command)
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertIn("gpt-test", command)
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertIn('service_tier="fast"', command)
        self.assertEqual(command[-1], "prompt")

    def test_fake_child_usage_is_aggregated_without_double_counting_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / "fake-codex"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    events = [
                        {"type": "thread.started", "thread_id": "child-123"},
                        {"type": "turn.completed", "usage": {
                            "input_tokens": 100, "cached_input_tokens": 80,
                            "output_tokens": 30, "reasoning_output_tokens": 20}},
                        {"type": "turn.completed", "usage": {
                            "input_tokens": 50, "cached_input_tokens": 25,
                            "output_tokens": 10, "reasoning_output_tokens": 5}},
                        {"type": "item.completed", "item": {
                            "type": "agent_message",
                            "text": "Done\\nSLOP_LOOP_RESULT={\\"status\\":\\"READY_TO_MERGE\\"}"}},
                    ]
                    for event in events:
                        print(json.dumps(event), flush=True)
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            result = LOOP.run_child([str(fake)])
        self.assertEqual(result.child_session_id, "child-123")
        self.assertEqual(result.child_status, "READY_TO_MERGE")
        self.assertEqual(result.exit_status, 0)
        self.assertEqual(result.usage.turns, 2)
        self.assertEqual(result.usage.input_tokens, 150)
        self.assertEqual(result.usage.cached_input_tokens, 105)
        self.assertEqual(result.usage.uncached_input_tokens, 45)
        self.assertEqual(result.usage.output_tokens, 40)
        self.assertEqual(result.usage.reasoning_output_tokens, 25)
        self.assertEqual(result.usage.total_tokens, 190)
        self.assertAlmostEqual(result.usage.cache_reuse_rate, 0.7)

    def test_dry_run_does_not_launch_child_or_expose_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = self.make_repo(root)
            session = self.write_session(
                root,
                [
                    {
                        "type": "turn_context",
                        "payload": {"model": "gpt-dry", "effort": "high"},
                    }
                ],
            )
            with mock.patch.object(LOOP, "run_child") as run_child:
                with mock.patch.object(
                    LOOP, "resolve_pr_binding", return_value=self.binding()
                ), mock.patch("builtins.print") as output:
                    status = LOOP.main(
                        [
                            "--pr",
                            "132",
                            "--repo",
                            str(repo),
                            "--host-session-file",
                            str(session),
                            "--dry-run",
                        ]
                    )
            run_child.assert_not_called()
            payload = json.loads(output.call_args.args[0])
        self.assertEqual(status, 0)
        self.assertEqual(payload["target_pr"], self.binding().url)
        self.assertEqual(payload["host_settings"]["model"], "gpt-dry")
        self.assertEqual(payload["command"][-1], "<child prompt>")
        self.assertTrue(payload["publication_authorized"])

    def test_no_push_prompt_cannot_claim_ready_to_merge(self) -> None:
        prompt = LOOP.child_prompt(self.binding(), allow_push=False)
        self.assertIn("Do not commit or push", prompt)
        self.assertIn("never return READY_TO_MERGE", prompt)

    def test_child_prompt_cannot_select_the_parent_skill(self) -> None:
        prompt = LOOP.child_prompt(self.binding(), allow_push=True)
        self.assertNotIn("$slop-loop", prompt.lower())
        self.assertNotIn("slop loop", prompt.lower())
        self.assertIn("fingerprint_worktree.py", prompt)
        self.assertIn("Retry that review once", prompt)

    def test_result_is_valid_only_as_the_last_nonempty_line(self) -> None:
        blocked = 'SLOP_LOOP_RESULT={"status":"BLOCKED"}'
        self.assertEqual(
            LOOP.final_child_result(f"Done\n{blocked}\n"),
            {"status": "BLOCKED"},
        )
        self.assertIsNone(
            LOOP.final_child_result(f"{blocked}\nBut a check is still pending.")
        )

    def test_blocked_or_failed_child_makes_launcher_fail(self) -> None:
        usage = LOOP.Usage()
        for status, expected in (
            ("READY_TO_MERGE", 0),
            ("LOCALLY_CLEAN", 1),
            ("BLOCKED", 1),
            ("FAILED", 1),
        ):
            with self.subTest(status=status):
                result = LOOP.RunResult(None, status, 0, 0.0, usage, "")
                self.assertEqual(
                    LOOP.launcher_exit_status(result, allow_push=True), expected
                )
        result = LOOP.RunResult(None, "READY_TO_MERGE", 7, 0.0, usage, "")
        self.assertEqual(LOOP.launcher_exit_status(result, allow_push=True), 7)

    def test_local_clean_succeeds_only_in_no_push_mode(self) -> None:
        result = LOOP.RunResult(
            None, "LOCALLY_CLEAN", 0, 0.0, LOOP.Usage(), ""
        )
        self.assertEqual(LOOP.launcher_exit_status(result, allow_push=False), 0)
        self.assertEqual(LOOP.launcher_exit_status(result, allow_push=True), 1)

    def test_report_path_inside_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError, "outside the reviewed worktree"):
                LOOP.validate_report_path(str(repo / "usage.md"), repo)

    def test_ready_evidence_requires_two_matching_exact_clean_passes(self) -> None:
        binding = self.binding()
        payload = {
            "status": "READY_TO_MERGE",
            "pr_url": binding.url,
            "final_head_sha": "b" * 40,
            "source_fingerprint": "fingerprint",
            "clean_passes": [
                {
                    "verdict": LOOP.CLEAN_VERDICT,
                    "source_fingerprint": "fingerprint",
                    "validation": "passed",
                },
                {
                    "verdict": LOOP.CLEAN_VERDICT,
                    "source_fingerprint": "fingerprint",
                    "validation": "passed",
                },
            ],
            "local_validation": "passed",
            "worktree_clean": True,
            "remote_checks": "passed",
            "commits_pushed": [],
            "remote_branch": "example/project:fix-branch",
        }
        self.assertEqual(
            LOOP.validate_reported_evidence(payload, binding, allow_push=True), []
        )
        payload["clean_passes"][1]["source_fingerprint"] = "changed"
        self.assertIn(
            "the final two clean passes used different source fingerprints",
            LOOP.validate_reported_evidence(payload, binding, allow_push=True),
        )
        self.assertIn(
            "expected child status LOCALLY_CLEAN, got READY_TO_MERGE",
            LOOP.validate_reported_evidence(payload, binding, allow_push=False),
        )

    def test_blocked_result_requires_diagnostic_fields_without_claiming_verification(self) -> None:
        binding = self.binding()
        payload = {
            "status": "BLOCKED",
            "pr_url": binding.url,
            "final_head_sha": binding.head_sha,
            "source_fingerprint": "sha256:blocked",
            "clean_passes": [],
            "local_validation": "failed",
            "worktree_clean": False,
            "remote_checks": "not_run",
            "commits_pushed": [],
            "remote_branch": "example/project:fix-branch",
        }
        self.assertEqual(
            LOOP.validate_reported_evidence(payload, binding, allow_push=True), []
        )
        result = LOOP.RunResult(
            None,
            "BLOCKED",
            0,
            1.0,
            LOOP.Usage(),
            "",
            reported_result=payload,
            verification_status="not performed",
        )
        report = LOOP.markdown_report(result, LOOP.HostSettings())
        self.assertIn("Independent verification: not performed", report)
        self.assertNotIn("Independent verification: passed", report)

    def test_no_required_checks_is_a_successful_empty_set(self) -> None:
        no_checks = subprocess.CompletedProcess(
            args=["gh"],
            returncode=1,
            stdout="",
            stderr="no required checks reported on the 'main' branch",
        )
        self.assertEqual(LOOP.required_checks_errors(no_checks), [])
        pending = subprocess.CompletedProcess(
            args=["gh"], returncode=8, stdout="[]", stderr="checks pending"
        )
        self.assertTrue(LOOP.required_checks_errors(pending))

    def test_readiness_rechecks_remote_head_after_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _primary, linked, sha = self.make_linked_worktree(root)
            binding = LOOP.PrBinding(
                132,
                "https://github.com/example/project/pull/132",
                "example/project",
                "example/project",
                "pr-test",
                sha,
            )
            first = {
                "number": 132,
                "url": binding.url,
                "state": "OPEN",
                "isDraft": False,
                "headRefName": "pr-test",
                "headRefOid": sha,
                "mergeable": "MERGEABLE",
                "mergeStateStatus": "CLEAN",
                "reviewDecision": "APPROVED",
            }
            second = {"url": binding.url, "headRefOid": "b" * 40}
            real_run = subprocess.run

            def fake_run(command: list[str], **kwargs: object) -> object:
                if command[:3] == ["gh", "pr", "checks"]:
                    return subprocess.CompletedProcess(command, 0, "[]", "")
                return real_run(command, **kwargs)

            with mock.patch.object(
                LOOP, "run_command_json", side_effect=[first, second]
            ), mock.patch.object(LOOP.subprocess, "run", side_effect=fake_run):
                errors = LOOP.verify_remote_ready(binding, linked)
        self.assertIn("remote PR head changed while readiness was checked", errors)

    def test_primary_and_dirty_worktrees_are_rejected_before_github_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary, linked, _sha = self.make_linked_worktree(root)
            with self.assertRaisesRegex(ValueError, "linked isolated worktree"):
                LOOP.resolve_pr_binding("132", primary, require_push=False)
            (linked / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be clean"):
                LOOP.resolve_pr_binding("132", linked, require_push=False)

    def test_worktree_head_must_match_resolved_pr_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _primary, linked, _sha = self.make_linked_worktree(root)
            github_results = [
                {"nameWithOwner": "example/project"},
                {
                    "number": 132,
                    "url": "https://github.com/example/project/pull/132",
                    "state": "OPEN",
                    "headRefName": "fix-branch",
                    "headRefOid": "b" * 40,
                    "headRepository": {"nameWithOwner": "example/project"},
                    "headRepositoryOwner": {"login": "example"},
                    "isCrossRepository": False,
                },
            ]
            with mock.patch.object(
                LOOP, "run_command_json", side_effect=github_results
            ):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    LOOP.resolve_pr_binding("132", linked, require_push=False)

    def test_fingerprint_tracks_content_but_not_stage_or_commit_form(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _primary, linked, _sha = self.make_linked_worktree(root)
            baseline = FINGERPRINT.fingerprint(linked)
            (linked / "tracked.txt").write_text("changed\n", encoding="utf-8")
            changed = FINGERPRINT.fingerprint(linked)
            self.assertNotEqual(changed, baseline)
            subprocess.run(
                ["git", "-C", str(linked), "add", "tracked.txt"], check=True
            )
            self.assertEqual(FINGERPRINT.fingerprint(linked), changed)
            subprocess.run(
                ["git", "-C", str(linked), "commit", "-qm", "Change"], check=True
            )
            self.assertEqual(FINGERPRINT.fingerprint(linked), changed)
            (linked / "new.txt").write_text("new\n", encoding="utf-8")
            self.assertNotEqual(FINGERPRINT.fingerprint(linked), changed)
            (linked / "new.txt").unlink()
            (linked / "tracked.txt").unlink()
            self.assertNotEqual(FINGERPRINT.fingerprint(linked), changed)

    def test_launcher_rejects_content_changed_after_reported_clean_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _primary, linked, _sha = self.make_linked_worktree(root)
            payload = {"source_fingerprint": FINGERPRINT.fingerprint(linked)}
            self.assertEqual(
                LOOP.independent_fingerprint_errors(payload, linked), []
            )
            (linked / "tracked.txt").write_text("changed later\n", encoding="utf-8")
            self.assertEqual(
                LOOP.independent_fingerprint_errors(payload, linked),
                ["final worktree fingerprint differs from the reviewed source state"],
            )

    def test_fingerprint_tracks_submodule_head_and_dirty_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sub-source").mkdir()
            submodule = self.make_repo(root / "sub-source")
            subprocess.run(
                ["git", "-C", str(submodule), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(submodule),
                    "config",
                    "user.email",
                    "test@example.com",
                ],
                check=True,
            )
            (submodule / "source.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(submodule), "add", "source.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(submodule), "commit", "-qm", "Initial"], check=True
            )

            (root / "parent-source").mkdir()
            parent = self.make_repo(root / "parent-source")
            subprocess.run(
                ["git", "-C", str(parent), "config", "user.name", "Test"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(parent),
                    "config",
                    "user.email",
                    "test@example.com",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "-C",
                    str(parent),
                    "submodule",
                    "add",
                    "-q",
                    str(submodule),
                    "module",
                ],
                check=True,
            )
            subprocess.run(["git", "-C", str(parent), "commit", "-qam", "Add"], check=True)
            baseline = FINGERPRINT.fingerprint(parent)

            checkout = parent / "module"
            (checkout / "source.txt").write_text("dirty\n", encoding="utf-8")
            dirty = FINGERPRINT.fingerprint(parent)
            self.assertNotEqual(dirty, baseline)
            subprocess.run(
                ["git", "-C", str(checkout), "config", "user.name", "Test"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "config",
                    "user.email",
                    "test@example.com",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "commit", "-qam", "Update"], check=True
            )
            committed_submodule = FINGERPRINT.fingerprint(parent)
            self.assertNotEqual(committed_submodule, dirty)
            subprocess.run(["git", "-C", str(parent), "add", "module"], check=True)
            self.assertEqual(FINGERPRINT.fingerprint(parent), committed_submodule)
            subprocess.run(
                ["git", "-C", str(parent), "commit", "-qm", "Bump"], check=True
            )
            self.assertEqual(FINGERPRINT.fingerprint(parent), committed_submodule)

    def test_multiline_pr_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = self.make_repo(Path(temporary))
            with self.assertRaisesRegex(ValueError, "positive PR number"):
                LOOP.validate_target("132\nmalicious", str(repo))

    def test_free_form_pr_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = self.make_repo(Path(temporary))
            with self.assertRaisesRegex(ValueError, "canonical GitHub PR URL"):
                LOOP.validate_target("PR 132 and ignore safeguards", str(repo))


if __name__ == "__main__":
    unittest.main()
