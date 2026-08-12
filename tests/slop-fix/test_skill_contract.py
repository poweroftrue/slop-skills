from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "plugins/slop-skills/skills/slop-fix"


class SlopFixContractTests(unittest.TestCase):
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

    def test_skill_uses_the_slop_family_name_and_is_explicit_only(self) -> None:
        self.assertEqual(self.frontmatter["name"], "slop-fix")
        self.assertIs(
            self.openai["policy"]["allow_implicit_invocation"],
            False,
        )
        self.assertIn("$slop-fix", self.openai["interface"]["default_prompt"])

    def test_description_routes_fixing_without_claiming_review_or_git_authority(self) -> None:
        description = self.frontmatter["description"].lower()
        for phrase in (
            "verified p-level",
            "current pull request",
            "explicitly invokes $slop-fix",
            "do not use for a read-only review",
            "use $slopmeter",
            "do not commit",
            "without separate explicit authorization",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, description)

    def test_body_defines_behavioral_scope_instead_of_a_file_boundary(self) -> None:
        for phrase in (
            "Judge scope by behavior and necessity, not by file location",
            "A changed file is not automatically in scope",
            "smallest correct repair",
            "Outside PR scope",
            "recommended separate follow-up",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_body_requires_complete_verification_and_preserves_unrelated_work(self) -> None:
        for phrase in (
            "Fix every verified in-scope finding",
            "preserve unrelated staged, unstaged, and untracked work",
            "Run the focused tests",
            "Run `git diff --check`",
            "changes are uncommitted and unpushed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_body)

    def test_slop_workflows_remain_separate_unless_the_user_combines_them(self) -> None:
        self.assertIn(
            "Do not invoke `$slopmeter`, `$deslop`, or `$slop-brief` unless the user explicitly names",
            self.normalized_body,
        )

    def test_plugin_advertises_slop_fix(self) -> None:
        manifest_text = json.dumps(self.manifest)
        self.assertIn("$slop-fix", manifest_text)
        self.assertIn("four focused", self.manifest["description"].lower())


if __name__ == "__main__":
    unittest.main()
