from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT
    / "plugins/slop-skills/skills/slop-brief/scripts/publish_slop_brief.py"
)
SPEC = importlib.util.spec_from_file_location("publish_slop_brief", SCRIPT_PATH)
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)

BRIEF = """**What this PR changes:** Checkout now stops before fulfillment when the store wallet is short.

## Dictionary

- Wallet — A store's available spending balance.

## Changes in logical order

- **1. Safer checkout**
  - Stops an order before fulfillment when the wallet is short.
  - Files: `app/services/checkout.rb`.
"""


class BriefInputTests(unittest.TestCase):
    def read(self, value: str) -> str:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            return publisher.read_brief(handle.name)

    def test_accepts_complete_brief(self) -> None:
        self.assertEqual(self.read(f"\n{BRIEF}\n"), BRIEF.strip())

    def test_rejects_empty_or_incomplete_brief(self) -> None:
        for value in (
            "",
            "## Dictionary\n\n- Term — Meaning.",
            "**What this PR changes:**\n\n## Dictionary\n\n## Changes in logical order",
            "## Dictionary\n\n**What this PR changes:** Too late.\n\n## Changes in logical order",
        ):
            with self.subTest(value=value), self.assertRaises(publisher.PublishError):
                self.read(value)

    def test_rejects_reversed_headings_and_injected_markers(self) -> None:
        values = (
            "## Changes in logical order\n\n## Dictionary",
            f"{BRIEF}\n{publisher.START_MARKER}",
            f"{BRIEF}\n{publisher.LEGACY_END_MARKER}",
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(publisher.PublishError):
                self.read(value)


class MergeDescriptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section = publisher.managed_section(BRIEF.strip())

    def test_creates_section_without_losing_existing_body(self) -> None:
        updated, action = publisher.merge_description("Why this PR exists.\n", self.section)

        self.assertEqual(action, "created")
        self.assertTrue(updated.startswith("Why this PR exists.\n\n"))
        self.assertTrue(updated.endswith(self.section))

    def test_updates_only_managed_section(self) -> None:
        old = publisher.managed_section(BRIEF.replace("Safer checkout", "Old checkout").strip())
        body = f"Before\n\n{old}\n\nAfter"

        updated, action = publisher.merge_description(body, self.section)

        self.assertEqual(action, "updated")
        self.assertEqual(updated, f"Before\n\n{self.section}\n\nAfter")

    def test_reports_unchanged_section(self) -> None:
        body = f"Before\n\n{self.section}"
        updated, action = publisher.merge_description(body, self.section)

        self.assertEqual((updated, action), (body, "unchanged"))

    def test_migrates_legacy_change_brief_markers(self) -> None:
        legacy = (
            f"{publisher.LEGACY_START_MARKER}\n## Change Brief\n\nOld"
            f"\n{publisher.LEGACY_END_MARKER}"
        )
        updated, action = publisher.merge_description(f"Before\n\n{legacy}\n\nAfter", self.section)

        self.assertEqual(action, "migrated")
        self.assertNotIn("change-brief", updated)
        self.assertEqual(updated, f"Before\n\n{self.section}\n\nAfter")

    def test_rejects_incomplete_duplicate_conflicting_and_reversed_markers(self) -> None:
        malformed = (
            publisher.START_MARKER,
            publisher.END_MARKER,
            f"{self.section}\n{self.section}",
            (
                f"{self.section}\n{publisher.LEGACY_START_MARKER}\n"
                f"old\n{publisher.LEGACY_END_MARKER}"
            ),
            f"{publisher.END_MARKER}\ntext\n{publisher.START_MARKER}",
        )
        for body in malformed:
            with self.subTest(body=body), self.assertRaises(publisher.PublishError):
                publisher.merge_description(body, self.section)


class MainTests(unittest.TestCase):
    def invoke(
        self,
        metadata: dict[str, object],
        *,
        extra_args: tuple[str, ...] = (),
    ) -> tuple[int, list[tuple[tuple[str, ...], str | None]], str, str]:
        calls: list[tuple[tuple[str, ...], str | None]] = []

        def fake_run_gh(*args: str, stdin: str | None = None) -> str:
            calls.append((args, stdin))
            if args[:2] == ("pr", "view"):
                return json.dumps(metadata)
            return "{}"

        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write(BRIEF)
            handle.flush()
            argv = [
                str(SCRIPT_PATH),
                "--pr",
                "125",
                "--brief-file",
                handle.name,
                *extra_args,
            ]
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(sys, "argv", argv),
                patch.object(publisher, "run_gh", side_effect=fake_run_gh),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = publisher.main()
        return result, calls, stdout.getvalue(), stderr.getvalue()

    def metadata(self, *, state: str = "OPEN", body: str = "Existing") -> dict[str, object]:
        return {
            "number": 125,
            "state": state,
            "url": "https://github.com/poweroftrue/slop-skills/pull/125",
            "body": body,
        }

    def test_open_pr_is_patched_through_api(self) -> None:
        result, calls, stdout, stderr = self.invoke(self.metadata())

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[1][0],
            (
                "api",
                "--method",
                "PATCH",
                "repos/poweroftrue/slop-skills/pulls/125",
                "--input",
                "-",
            ),
        )
        payload = json.loads(calls[1][1] or "{}")
        self.assertIn(publisher.START_MARKER, payload["body"])
        self.assertEqual(json.loads(stdout)["action"], "created")

    def test_dry_run_never_patches(self) -> None:
        result, calls, stdout, stderr = self.invoke(
            self.metadata(), extra_args=("--dry-run",)
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn(publisher.START_MARKER, stdout)
        self.assertEqual(json.loads(stderr)["action"], "created")

    def test_closed_pr_is_rejected_without_override(self) -> None:
        result, calls, _stdout, stderr = self.invoke(self.metadata(state="MERGED"))

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("refusing to update", stderr)

    def test_closed_pr_can_be_explicitly_overridden(self) -> None:
        result, calls, _stdout, _stderr = self.invoke(
            self.metadata(state="CLOSED"), extra_args=("--allow-closed",)
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 2)

    def test_unchanged_pr_does_not_patch(self) -> None:
        body = publisher.managed_section(BRIEF.strip())
        result, calls, stdout, _stderr = self.invoke(self.metadata(body=body))

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(stdout)["action"], "unchanged")


if __name__ == "__main__":
    unittest.main()
