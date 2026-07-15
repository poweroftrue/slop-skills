#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REGISTRY="$SCRIPT_DIR/cases.json"
FIXTURES="$SCRIPT_DIR/fixtures"
SKILL="$REPO_ROOT/plugins/slop-skills/skills/slopmeter/SKILL.md"
CODEX_BIN="${CODEX_BIN:-codex}"
MODE="run"
SELECTED_CASE=""

usage() {
  cat <<'EOF'
Usage: tests/slopmeter/run_e2e.sh [--list | --validate | --case CASE_ID]

With no option, runs every owner-approved regression case.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)
      MODE="list"
      shift
      ;;
    --validate)
      MODE="validate"
      shift
      ;;
    --case)
      [[ $# -ge 2 ]] || fail "--case requires a case id"
      SELECTED_CASE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

validate_registry() {
  command -v git >/dev/null || fail "git is required"
  command -v jq >/dev/null || fail "jq is required"
  command -v ruby >/dev/null || fail "Ruby is required"
  [[ -f "$SKILL" ]] || fail "canonical Slopmeter skill not found: $SKILL"

  jq -e '
    .schema_version == 1 and
    (.governance | type == "string" and length > 0) and
    (.cases | type == "array" and length > 0) and
    ([.cases[].id] | length == (unique | length)) and
    all(.cases[];
      (.id | test("^[a-z0-9]+(-[a-z0-9]+)*$")) and
      (.fixture | type == "string" and length > 0) and
      (.prompt | type == "string" and length > 0) and
      (.expect.verdict == "clean" or .expect.verdict == "finding") and
      (if .expect.verdict == "finding"
       then (.expect.must_match | type == "array" and length > 0)
       else (.expect | keys == ["verdict"])
       end)
    )
  ' "$REGISTRY" >/dev/null || fail "invalid case registry"

  local case_id fixture
  for case_id in $(jq -r '.cases[].id' "$REGISTRY"); do
    fixture="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .fixture' "$REGISTRY")"
    [[ -d "$FIXTURES/$fixture/base" ]] || fail "$case_id is missing its base fixture"
    [[ -d "$FIXTURES/$fixture/head" ]] || fail "$case_id is missing its head fixture"
    find "$FIXTURES/$fixture/base" -type f -print -quit | grep -q . || fail "$case_id has an empty base fixture"
    find "$FIXTURES/$fixture/head" -type f -print -quit | grep -q . || fail "$case_id has an empty head fixture"
  done
}

list_cases() {
  jq -r '.cases[] | [.id, .expect.verdict] | @tsv' "$REGISTRY" |
    while IFS=$'\t' read -r case_id verdict; do
      printf '%-40s %s\n' "$case_id" "$verdict"
    done
}

materialize_fixture() {
  local fixture="$1"
  local destination="$2"

  mkdir -p "$destination"
  cp -R "$FIXTURES/$fixture/base/." "$destination/"
  git -C "$destination" init -q -b main
  git -C "$destination" config user.name "Slopmeter E2E"
  git -C "$destination" config user.email "slopmeter-e2e@example.invalid"
  git -C "$destination" config core.hooksPath /dev/null
  git -C "$destination" add -A
  git -C "$destination" -c commit.gpgsign=false commit -q -m "Base fixture"
  git -C "$destination" switch -q -c candidate
  cp -R "$FIXTURES/$fixture/head/." "$destination/"
  git -C "$destination" add -A
  git -C "$destination" -c commit.gpgsign=false commit -q -m "Candidate change"
}

extract_final_message() {
  jq -sr '
    [.[] | select(.type == "item.completed" and .item.type == "agent_message") | .item.text]
    | last // ""
  ' "$1"
}

assert_finding_contract() {
  local output="$1"
  local heading_count

  [[ "$output" =~ ^1\.\ \*\*P[012]\ \— ]] || return 1
  [[ "$output" == *"Status: ❌ Open"* ]] || return 1
  [[ "$output" == *"Technical problem:"* ]] || return 1
  [[ "$output" == *"Technical solution:"* ]] || return 1
  [[ "$output" == *"Product impact:"* ]] || return 1
  [[ "$output" == *"Product solution:"* ]] || return 1
  heading_count="$(printf '%s\n' "$output" | grep -Ec '^[0-9]+\. \*\*P[012]')"
  [[ "$heading_count" -eq 1 ]]
}

assert_pattern() {
  local pattern="$1"
  local output="$2"
  printf '%s' "$output" | ruby -e 'pattern = Regexp.new(ARGV.fetch(0)); exit(pattern.match?(STDIN.read) ? 0 : 1)' "$pattern"
}

run_case() {
  local case_id="$1"
  local case_json fixture prompt verdict workdir fixture_repo prompt_file events output pattern

  case_json="$(jq -c --arg id "$case_id" '.cases[] | select(.id == $id)' "$REGISTRY")"
  [[ -n "$case_json" ]] || fail "unknown case: $case_id"
  fixture="$(jq -r '.fixture' <<<"$case_json")"
  prompt="$(jq -r '.prompt' <<<"$case_json")"
  verdict="$(jq -r '.expect.verdict' <<<"$case_json")"
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slopmeter-e2e.XXXXXX")"
  fixture_repo="$workdir/repo"
  prompt_file="$workdir/prompt.txt"
  events="$workdir/events.jsonl"

  materialize_fixture "$fixture" "$fixture_repo"
  {
    printf '%s\n' 'Follow the exact Slopmeter skill instructions below as the active review procedure.'
    printf '%s\n' '<slopmeter-skill>'
    cat "$SKILL"
    printf '%s\n' '</slopmeter-skill>'
    printf '\nUser request:\n%s\n' "$prompt"
  } >"$prompt_file"

  printf 'RUN  %s\n' "$case_id"
  if ! "$CODEX_BIN" exec \
    --ephemeral \
    --ignore-user-config \
    --ignore-rules \
    --sandbox read-only \
    -c 'model_reasoning_effort="high"' \
    --cd "$fixture_repo" \
    --json \
    - <"$prompt_file" >"$events"; then
    printf 'FAIL %s (Codex execution failed; artifacts: %s)\n' "$case_id" "$workdir" >&2
    return 1
  fi

  output="$(extract_final_message "$events")"
  if [[ "$verdict" == "clean" ]]; then
    if [[ "$output" != "No open product-impacting findings." ]]; then
      printf 'FAIL %s (expected clean)\n%s\n' "$case_id" "$output" >&2
      printf 'Artifacts: %s\n' "$workdir" >&2
      return 1
    fi
  else
    if ! assert_finding_contract "$output"; then
      printf 'FAIL %s (finding contract mismatch)\n%s\n' "$case_id" "$output" >&2
      printf 'Artifacts: %s\n' "$workdir" >&2
      return 1
    fi
    while IFS= read -r pattern; do
      if ! assert_pattern "$pattern" "$output"; then
        printf 'FAIL %s (missing expected evidence pattern: %s)\n%s\n' "$case_id" "$pattern" "$output" >&2
        printf 'Artifacts: %s\n' "$workdir" >&2
        return 1
      fi
    done < <(jq -r '.expect.must_match[]' <<<"$case_json")
  fi

  printf 'PASS %s\n' "$case_id"
  rm -rf "$workdir"
}

validate_registry

if [[ "$MODE" == "list" ]]; then
  list_cases
  exit 0
fi

if [[ "$MODE" == "validate" ]]; then
  printf 'Registry and fixtures are valid.\n'
  exit 0
fi

command -v "$CODEX_BIN" >/dev/null || fail "Codex CLI is required: $CODEX_BIN"

if [[ -n "$SELECTED_CASE" ]]; then
  run_case "$SELECTED_CASE"
else
  failures=0
  for case_id in $(jq -r '.cases[].id' "$REGISTRY"); do
    if ! run_case "$case_id"; then
      failures=$((failures + 1))
    fi
  done
  [[ "$failures" -eq 0 ]] || fail "$failures Slopmeter regression case(s) failed"
fi

printf 'All selected Slopmeter regressions passed.\n'
