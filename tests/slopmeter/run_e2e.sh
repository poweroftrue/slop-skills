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
      (if has("head")
       then (.head | type == "string" and test("^[a-z0-9]+(-[a-z0-9]+)*$"))
       else true
       end) and
      (if has("runtime")
       then (.runtime == "docker")
       else true
       end) and
      (.prompt | type == "string" and length > 0) and
      (.expect | type == "object") and
      ((.expect | keys - ["finding_count", "must_execute", "must_match", "must_not_execute", "verdict"]) | length == 0) and
      (.expect.verdict == "clean" or .expect.verdict == "finding") and
      (if .expect.verdict == "finding"
       then (
         (.expect.must_match | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)) and
         (if (.expect | has("finding_count"))
          then (
            (.expect.finding_count | type == "number" and floor == . and . > 0) or
            (
              (.expect.finding_count | type == "array" and length > 0) and
              (.expect.finding_count | length == (unique | length)) and
              all(.expect.finding_count[]; type == "number" and floor == . and . > 0)
            )
          )
          else true
          end)
       )
       else (
         ((.expect | has("must_match")) | not) and
         ((.expect | has("finding_count")) | not)
       )
       end) and
      (if (.expect | has("must_execute"))
       then (.expect.must_execute | type == "array" and length > 0 and all(.[]; type == "string" and length > 0))
       else true
       end) and
      (if (.expect | has("must_not_execute"))
       then (.expect.must_not_execute | type == "array" and length > 0 and all(.[]; type == "string" and length > 0))
       else true
       end)
    )
  ' "$REGISTRY" >/dev/null || fail "invalid case registry"

  local case_id fixture head
  for case_id in $(jq -r '.cases[].id' "$REGISTRY"); do
    fixture="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .fixture' "$REGISTRY")"
    head="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .head // "head"' "$REGISTRY")"
    [[ -d "$FIXTURES/$fixture/base" ]] || fail "$case_id is missing its base fixture"
    [[ -d "$FIXTURES/$fixture/$head" ]] || fail "$case_id is missing its $head head fixture"
    find "$FIXTURES/$fixture/base" -type f -print -quit | grep -q . || fail "$case_id has an empty base fixture"
    find "$FIXTURES/$fixture/$head" -type f -print -quit | grep -q . || fail "$case_id has an empty $head head fixture"
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
  local head="$2"
  local destination="$3"

  mkdir -p "$destination"
  cp -R "$FIXTURES/$fixture/base/." "$destination/"
  git -C "$destination" init -q -b main
  git -C "$destination" config user.name "Slopmeter E2E"
  git -C "$destination" config user.email "slopmeter-e2e@example.invalid"
  git -C "$destination" config core.hooksPath /dev/null
  git -C "$destination" add -A
  git -C "$destination" -c commit.gpgsign=false commit -q -m "Base fixture"
  git -C "$destination" switch -q -c candidate
  cp -R "$FIXTURES/$fixture/$head/." "$destination/"
  git -C "$destination" add -A
  git -C "$destination" -c commit.gpgsign=false commit -q -m "Candidate change"
}

extract_final_message() {
  jq -sr '
    [.[] | select(.type == "item.completed" and .item.type == "agent_message") | .item.text]
    | last // ""
  ' "$1"
}

extract_command_trace() {
  jq -sr '
    [
      .[]
      | select((.type == "item.started" or .type == "item.completed") and .item.type == "command_execution")
      | .item.command
      | select(type == "string")
    ]
    | unique
    | join("\n")
  ' "$1"
}

assert_finding_contract() {
  local output="$1"
  local expected_counts="$2"
  local heading_count status_count problem_count solution_count impact_count product_solution_count

  [[ "$output" =~ ^1\.\ \*\*P[012]\ \— ]] || return 1
  heading_count="$(printf '%s\n' "$output" | grep -Ec '^[0-9]+\. \*\*P[012]')"
  [[ ",$expected_counts," == *",$heading_count,"* ]] || return 1
  status_count="$(printf '%s\n' "$output" | grep -Fc 'Status: ❌ Open')"
  problem_count="$(printf '%s\n' "$output" | grep -Fc 'Technical problem:')"
  solution_count="$(printf '%s\n' "$output" | grep -Fc 'Technical solution:')"
  impact_count="$(printf '%s\n' "$output" | grep -Fc 'Product impact:')"
  product_solution_count="$(printf '%s\n' "$output" | grep -Fc 'Product solution:')"
  [[ "$status_count" -eq "$heading_count" ]] &&
    [[ "$problem_count" -eq "$heading_count" ]] &&
    [[ "$solution_count" -eq "$heading_count" ]] &&
    [[ "$impact_count" -eq "$heading_count" ]] &&
    [[ "$product_solution_count" -eq "$heading_count" ]] &&
    printf '%s\n' "$output" |
      ruby -e 'expected = Integer(ARGV.fetch(0)); numbers = STDIN.read.scan(/^(\d+)\. \*\*P[012] —/).flatten.map(&:to_i); exit(numbers == (1..expected).to_a ? 0 : 1)' "$heading_count"
}

assert_pattern() {
  local pattern="$1"
  local output="$2"
  printf '%s' "$output" | ruby -e 'pattern = Regexp.new(ARGV.fetch(0)); exit(pattern.match?(STDIN.read) ? 0 : 1)' "$pattern"
}

run_case() {
  local case_id="$1"
  local case_json fixture head runtime prompt verdict finding_counts workdir fixture_repo prompt_file events output command_trace pattern
  local docker_host docker_socket
  local -a codex_args

  case_json="$(jq -c --arg id "$case_id" '.cases[] | select(.id == $id)' "$REGISTRY")"
  [[ -n "$case_json" ]] || fail "unknown case: $case_id"
  fixture="$(jq -r '.fixture' <<<"$case_json")"
  head="$(jq -r '.head // "head"' <<<"$case_json")"
  runtime="$(jq -r '.runtime // "read-only"' <<<"$case_json")"
  prompt="$(jq -r '.prompt' <<<"$case_json")"
  verdict="$(jq -r '.expect.verdict' <<<"$case_json")"
  finding_counts="$(jq -r '
    (.expect.finding_count // 1) |
    if type == "array" then map(tostring) | join(",") else tostring end
  ' <<<"$case_json")"
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slopmeter-e2e.XXXXXX")"
  fixture_repo="$workdir/repo"
  prompt_file="$workdir/prompt.txt"
  events="$workdir/events.jsonl"

  materialize_fixture "$fixture" "$head" "$fixture_repo"
  {
    printf '%s\n' 'Follow the exact Slopmeter skill instructions below as the active review procedure.'
    printf '%s\n' '<slopmeter-skill>'
    cat "$SKILL"
    printf '%s\n' '</slopmeter-skill>'
    printf '\nUser request:\n%s\n' "$prompt"
  } >"$prompt_file"

  printf 'RUN  %s\n' "$case_id"
  codex_args=(
    exec
    --ephemeral
    --ignore-user-config
    --ignore-rules
    -c 'model_reasoning_effort="high"'
  )
  if [[ "$runtime" == "docker" ]]; then
    command -v docker >/dev/null || fail "$case_id requires Docker"
    docker_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" ||
      fail "$case_id could not resolve the active Docker context"
    [[ "$docker_host" == unix://* ]] ||
      fail "$case_id requires a local Unix-socket Docker context"
    docker_socket="${docker_host#unix://}"
    [[ -S "$docker_socket" && "$docker_socket" != *'"'* ]] ||
      fail "$case_id resolved an invalid Docker socket"
    docker image inspect postgres:16-alpine >/dev/null 2>&1 ||
      fail "$case_id requires the preloaded postgres:16-alpine image"
    codex_args+=(
      -c 'default_permissions="slopmeter-e2e-docker"'
      -c 'permissions.slopmeter-e2e-docker.extends=":read-only"'
      -c 'permissions.slopmeter-e2e-docker.network.enabled=true'
      -c "permissions.slopmeter-e2e-docker.network.unix_sockets={\"$docker_socket\"=\"allow\"}"
    )
  else
    codex_args+=(--sandbox read-only)
  fi
  codex_args+=(--cd "$fixture_repo" --json -)

  if ! "$CODEX_BIN" "${codex_args[@]}" <"$prompt_file" >"$events"; then
    printf 'FAIL %s (Codex execution failed; artifacts: %s)\n' "$case_id" "$workdir" >&2
    return 1
  fi

  output="$(extract_final_message "$events")"
  command_trace="$(extract_command_trace "$events")"
  while IFS= read -r pattern; do
    if ! assert_pattern "$pattern" "$command_trace"; then
      printf 'FAIL %s (required command was not executed: %s)\n' "$case_id" "$pattern" >&2
      printf 'Command trace:\n%s\n' "$command_trace" >&2
      printf 'Artifacts: %s\n' "$workdir" >&2
      return 1
    fi
  done < <(jq -r '.expect.must_execute[]?' <<<"$case_json")

  while IFS= read -r pattern; do
    if assert_pattern "$pattern" "$command_trace"; then
      printf 'FAIL %s (forbidden command was executed: %s)\n' "$case_id" "$pattern" >&2
      printf 'Command trace:\n%s\n' "$command_trace" >&2
      printf 'Artifacts: %s\n' "$workdir" >&2
      return 1
    fi
  done < <(jq -r '.expect.must_not_execute[]?' <<<"$case_json")

  if [[ "$verdict" == "clean" ]]; then
    if [[ "$output" != "No open product-impacting findings." ]]; then
      printf 'FAIL %s (expected clean)\n%s\n' "$case_id" "$output" >&2
      printf 'Artifacts: %s\n' "$workdir" >&2
      return 1
    fi
  else
    if ! assert_finding_contract "$output" "$finding_counts"; then
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
