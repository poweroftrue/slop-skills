from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PRIME_AGENT_ROOT = Path("/opt/homebrew/lib/node_modules/prime-agent")
PI_TUI = PRIME_AGENT_ROOT / "node_modules/@earendil-works/pi-tui/dist/index.js"

OLD_SAMPLE = """1. **P2 — Retry window ends too early**
   **Status: ❌ Open**

   **Technical problem:** A delayed retry expected 1 queued attempt, got 0.

   **Technical solution:** Start a fresh bounded retry window.

   **Product impact:** A customer order can stop after one temporary failure.

   **Product solution:** Temporary failures must use the normal retry window.
"""

NEW_SAMPLE = """## Change context

Storefront PR #42 changes checkout retries so temporary provider failures recover.

## Finding 1 — P2 — Retry window ends too early

**Status:** ❌ Open

**Technical problem:** A delayed retry expected 1 queued attempt, got 0.

**Technical solution:** Start a fresh bounded retry window.

**Product impact:** A customer order can stop after one temporary failure.

**Product solution:** Temporary failures must use the normal retry window.
"""


@unittest.skipUnless(shutil.which("node") and PI_TUI.is_file(), "Prime Agent renderer unavailable")
class PrimeRenderingTests(unittest.TestCase):
    def render(self, text: str) -> list[str]:
        script = rf"""
import {{ Markdown }} from {json.dumps(PI_TUI.as_uri())};
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const identity = (value) => value;
const theme = {{
  heading: identity, link: identity, linkUrl: identity, code: identity,
  codeBlock: identity, codeBlockBorder: identity, quote: identity,
  quoteBorder: identity, hr: identity, listBullet: identity, bold: identity,
  italic: identity, strikethrough: identity, underline: identity,
}};
for (const line of new Markdown(chunks.join(""), 1, 0, theme).render(88)) {{
  console.log(line.replace(/\x1b\[[0-9;]*m/g, "").trimEnd());
}}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as file:
            file.write(script)
            script_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(script_path)],
                input=text,
                text=True,
                capture_output=True,
                check=True,
            )
        finally:
            script_path.unlink(missing_ok=True)
        return result.stdout.splitlines()

    def test_flat_sections_remove_list_continuation_indentation(self) -> None:
        old_lines = self.render(OLD_SAMPLE)
        new_lines = self.render(NEW_SAMPLE)
        self.assertTrue(any(line.startswith("   ") for line in old_lines))
        self.assertFalse(any(line.startswith("   ") for line in new_lines))
        self.assertTrue(any("Change context" in line for line in new_lines))
        self.assertTrue(any("Finding 1 — P2" in line for line in new_lines))


if __name__ == "__main__":
    unittest.main()
