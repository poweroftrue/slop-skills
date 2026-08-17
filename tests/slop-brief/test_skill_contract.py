from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "plugins/slop-skills/skills/slop-brief"


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", skill_text, re.DOTALL)
        assert match
        cls.frontmatter = yaml.safe_load(match.group(1))
        cls.body = match.group(2)
        cls.openai = yaml.safe_load(
            (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (REPO_ROOT / "plugins/slop-skills/.codex-plugin/plugin.json").read_text(
                encoding="utf-8"
            )
        )

    def test_skill_is_implicitly_invocable(self) -> None:
        self.assertEqual(self.frontmatter["name"], "slop-brief")
        self.assertIs(self.openai["policy"]["allow_implicit_invocation"], True)
        self.assertIn("$slop-brief", self.openai["interface"]["default_prompt"])

    def test_description_covers_pr_lifecycle_and_branch_pushes(self) -> None:
        description = self.frontmatter["description"].lower()
        self.assertTrue(description.startswith("never use this skill"))
        for phrase in (
            "create",
            "review",
            "push",
            "branch",
            "feedback",
            "approve",
            "merge",
            "close",
            "reopen",
            "implicit read-only",
            "$slopmeter",
            "$deslop",
            "unless slop brief",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, description)

    def test_body_defines_automatic_sync_and_read_only_boundary(self) -> None:
        for phrase in (
            "Creating or mutating a PR",
            "Implicit read-only PR work",
            "Never turn a read-only request into a write",
            "Merge or close",
            "preserves all other PR body",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.body)

    def test_brief_starts_with_product_change_before_dictionary(self) -> None:
        summary = "**What this PR changes:**"
        dictionary = "## Dictionary"
        changes = "## Changes in logical order"
        self.assertIn(summary, self.body)
        self.assertLess(self.body.index(summary), self.body.index(dictionary))
        self.assertLess(self.body.index(dictionary), self.body.index(changes))

    def test_plugin_advertises_all_five_skills(self) -> None:
        interface = self.manifest["interface"]
        prompts = "\n".join(interface["defaultPrompt"])
        self.assertIn("$deslop", prompts)
        self.assertIn("$slopmeter", prompts)
        self.assertIn("$slop-brief", prompts)
        self.assertIn("$slop-fix", prompts)
        self.assertIn("$slop-loop", prompts)
        self.assertIn("pull request", self.manifest["description"].lower())


if __name__ == "__main__":
    unittest.main()
