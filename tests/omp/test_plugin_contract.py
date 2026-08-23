from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = REPO_ROOT / ".omp-plugin/marketplace.json"
EXPECTED_SKILLS = {"deslop", "slopmeter", "slop-fix", "slop-brief"}


def load_frontmatter(skill_file: Path) -> dict[str, object]:
    text = skill_file.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        raise AssertionError(f"invalid SKILL.md frontmatter: {skill_file}")
    return yaml.safe_load(match.group(1))


class OmpPluginContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        cls.plugin = cls.catalog["plugins"][0]
        cls.plugin_root = (REPO_ROOT / cls.plugin["source"]).resolve()
        cls.skill_root = cls.plugin_root / "skills"
        cls.frontmatter = {
            path.parent.name: load_frontmatter(path)
            for path in cls.skill_root.glob("*/SKILL.md")
        }

    def test_catalog_is_an_omp_marketplace(self) -> None:
        self.assertEqual(self.catalog["name"], "slop-skills")
        self.assertEqual(self.catalog["owner"]["name"], "poweroftrue")
        self.assertEqual(len(self.catalog["plugins"]), 1)
        self.assertEqual(self.plugin["name"], "slop-skills")
        self.assertEqual(self.plugin["source"], "./plugins/slop-skills")
        self.assertTrue(self.plugin_root.is_dir())
        self.assertTrue(self.plugin_root.is_relative_to(REPO_ROOT))

    def test_omp_discovers_all_canonical_skills(self) -> None:
        self.assertEqual(set(self.frontmatter), EXPECTED_SKILLS)
        for directory_name, metadata in self.frontmatter.items():
            with self.subTest(skill=directory_name):
                self.assertEqual(metadata["name"], directory_name)
                self.assertIsInstance(metadata.get("description"), str)
                self.assertTrue(str(metadata["description"]).strip())

    def test_shared_skills_avoid_omp_only_visibility_metadata(self) -> None:
        for skill_name, metadata in self.frontmatter.items():
            with self.subTest(skill=skill_name):
                self.assertNotIn("disable-model-invocation", metadata)
                self.assertNotIn("hide", metadata)

    def test_slop_fix_remains_explicit_and_non_mutating_outside_source(self) -> None:
        metadata = self.frontmatter["slop-fix"]
        description = str(metadata["description"]).lower()
        self.assertIn("explicitly invokes $slop-fix", description)
        self.assertIn("do not commit", description)
        self.assertIn("without separate explicit authorization", description)


if __name__ == "__main__":
    unittest.main()
