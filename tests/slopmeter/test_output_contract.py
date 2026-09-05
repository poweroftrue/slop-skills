from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "plugins/slop-skills/skills/slopmeter/SKILL.md"


class SlopmeterOutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_PATH.read_text(encoding="utf-8")
        cls.contract = cls.skill.split("## Final answer contract", 1)[1]

    def test_open_findings_start_with_change_context(self) -> None:
        self.assertIn("## Change context", self.contract)
        self.assertIn(
            "One concise sentence that identifies the reviewed change",
            self.contract,
        )
        self.assertLess(
            self.contract.index("## Change context"),
            self.contract.index("## Finding 1 — P#"),
        )
        template = re.search(
            r"## Change context\n\n([^\n]+)\n\n## Finding 1",
            self.contract,
        )
        self.assertIsNotNone(template)

    def test_findings_use_flat_sections_instead_of_one_nested_list(self) -> None:
        self.assertIn("## Finding 1 — P# — Product-readable title", self.contract)
        self.assertNotRegex(self.contract, r"(?m)^N\. \*\*P#")
        self.assertIn("**Status:**", self.contract)
        self.assertIn("**Technical problem:**", self.contract)
        self.assertIn("**Technical solution:**", self.contract)
        self.assertIn("**Product impact:**", self.contract)
        self.assertIn("**Product solution:**", self.contract)

    def test_context_is_specific_and_not_a_repeated_summary(self) -> None:
        for phrase in (
            "repository or product area",
            "pull request number, branch, or short change purpose",
            "Do not use a generic sentence",
            "do not repeat the context inside every finding",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.contract)

    def test_clean_verdict_remains_exact(self) -> None:
        self.assertIn(
            "For a fresh review with no supported open findings, write exactly: `No open product-impacting findings.`",
            self.skill,
        )


if __name__ == "__main__":
    unittest.main()
