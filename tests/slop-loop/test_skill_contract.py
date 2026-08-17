from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "plugins/slop-skills/skills/slop-loop"


class SlopLoopContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", skill_text, re.DOTALL)
        assert match
        cls.frontmatter = yaml.safe_load(match.group(1))
        cls.body = match.group(2)
        cls.normalized_body = " ".join(cls.body.split())
        cls.openai = yaml.safe_load(
            (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (REPO_ROOT / "plugins/slop-skills/.codex-plugin/plugin.json").read_text(
                encoding="utf-8"
            )
        )

    def test_skill_is_explicit_only_and_names_itself_in_the_prompt(self) -> None:
        self.assertEqual(self.frontmatter["name"], "slop-loop")
        self.assertIs(self.openai["policy"]["allow_implicit_invocation"], False)
        self.assertIn("$slop-loop", self.openai["interface"]["default_prompt"])

    def test_contract_has_both_child_workflows_and_exact_clean_gate(self) -> None:
        for phrase in (
            "$slop-skills:slopmeter",
            "$slop-skills:slop-fix",
            "No open product-impacting findings.",
            "two consecutive Slopmeter passes",
            "same source state",
            "set `clean_streak = 1`",
            "retry Slopmeter once on the unchanged source fingerprint",
            "stop as `FAILED`",
            "fingerprint_worktree.py",
            "initialized submodule",
            "staging or committing unchanged parent content does not change the fingerprint",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_contract_preserves_git_authority_boundary(self) -> None:
        for phrase in (
            "exact existing PR head branch",
            "Never merge, force-push, rebase published history",
            "Do not clean, reset, stash, overwrite, or delete user work",
            "READY_TO_MERGE",
            "LOCALLY_CLEAN",
            "BLOCKED",
            "FAILED",
            "A `--no-push` run does not require push access",
            "never commit, push, or require local-to-remote equality",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_failed_validation_cannot_advance_or_publish(self) -> None:
        for phrase in (
            "require every validation to pass before changing the streak or publishing",
            "do not increment, commit, or push",
            "every recorded repository-required and focused local validation succeeded",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_contract_requires_host_settings_and_usage_metrics(self) -> None:
        for phrase in (
            "CODEX_THREAD_ID",
            "model, reasoning effort, and service tier",
            "cached input tokens",
            "uncached input tokens",
            "cache reuse rate",
            "reasoning output tokens",
            "elapsed time",
            "SLOP_LOOP_RESULT=",
            "independent local and GitHub checks",
            "final worktree fingerprint that differs from the two reviewed clean passes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_contract_forbids_recursive_loop(self) -> None:
        self.assertIn("Do not run the loop in the host session", self.normalized_body)
        self.assertIn("invoke `$slop-loop` recursively", self.normalized_body)

    def test_plugin_advertises_slop_loop(self) -> None:
        manifest_text = json.dumps(self.manifest)
        self.assertIn("$slop-loop", manifest_text)
        self.assertIn("five focused", self.manifest["description"].lower())


if __name__ == "__main__":
    unittest.main()
