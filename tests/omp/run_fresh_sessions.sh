#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGIN_ROOT="$REPO_ROOT/plugins/slop-skills"
OMP_BIN="${OMP_BIN:-omp}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

extract_final_message() {
  jq -sr '
    [
      .[]
      | select(.type == "message_end" and .message.role == "assistant")
      | [.message.content[]? | select(.type == "text") | .text] | join("\n")
      | select(length > 0)
    ]
    | last // ""
  ' "$1"
}

read_skill_trace() {
  jq -sr '
    [
      .[]
      | select(.type == "tool_execution_start" and .toolName == "read")
      | .args.path // ""
    ]
    | join("\n")
  ' "$1"
}

run_probe() {
  local skill="$1"
  local prompt="$2"
  local expected="$3"
  local workdir events output trace normalized_output normalized_expected

  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slop-skills-omp-probe.XXXXXX")"
  events="$workdir/events.jsonl"
  printf 'RUN  explicit-%s\n' "$skill"
  if ! "$OMP_BIN" -p --mode json --no-session --no-title --no-rules \
    --max-time 2m --thinking high --tools read --plugin-dir "$PLUGIN_ROOT" \
    --skills "$skill" "/skill:$skill $prompt" >"$events"; then
    printf 'FAIL explicit-%s (OMP execution failed; artifacts: %s)\n' "$skill" "$workdir" >&2
    return 1
  fi
  output="$(extract_final_message "$events")"
  trace="$(read_skill_trace "$events")"
  normalized_output="$(printf '%s' "$output" | tr '[:upper:]' '[:lower:]')"
  normalized_expected="$(printf '%s' "$expected" | tr '[:upper:]' '[:lower:]')"
  if [[ "$trace" != *"skill://$skill"* ]]; then
    printf 'FAIL explicit-%s (skill was not loaded; artifacts: %s)\n' "$skill" "$workdir" >&2
    return 1
  fi
  if [[ "$normalized_output" != *"$normalized_expected"* ]]; then
    printf 'FAIL explicit-%s (expected %q; got %q; artifacts: %s)\n' \
      "$skill" "$expected" "$output" "$workdir" >&2
    return 1
  fi
  printf 'PASS explicit-%s\n' "$skill"
  rm -rf "$workdir"
}

run_implicit_probe() {
  local skill="$1"
  local prompt="$2"
  local workdir events trace

  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slop-skills-omp-implicit.XXXXXX")"
  events="$workdir/events.jsonl"
  printf 'RUN  implicit-%s\n' "$skill"
  if ! "$OMP_BIN" -p --mode json --no-session --no-title --no-rules \
    --max-time 2m --thinking high --tools read --plugin-dir "$PLUGIN_ROOT" \
    --skills "$skill" "$prompt" >"$events"; then
    printf 'FAIL implicit-%s (OMP execution failed; artifacts: %s)\n' "$skill" "$workdir" >&2
    return 1
  fi
  trace="$(read_skill_trace "$events")"
  if [[ "$trace" != *"skill://$skill"* ]]; then
    printf 'FAIL implicit-%s (skill was not selected; artifacts: %s)\n' "$skill" "$workdir" >&2
    return 1
  fi
  printf 'PASS implicit-%s\n' "$skill"
  rm -rf "$workdir"
}

run_read_only_boundary_probe() {
  local workdir events trace

  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slop-skills-omp-boundary.XXXXXX")"
  events="$workdir/events.jsonl"
  printf 'RUN  read-only-boundary-slop-fix\n'
  if ! "$OMP_BIN" -p --mode json --no-session --no-title --no-rules \
    --max-time 2m --thinking high --tools read --plugin-dir "$PLUGIN_ROOT" \
    --skills slop-fix \
    'Review this pull request without changing code. Do not inspect files; state that no target was supplied.' \
    >"$events"; then
    printf 'FAIL read-only-boundary-slop-fix (OMP execution failed; artifacts: %s)\n' "$workdir" >&2
    return 1
  fi
  trace="$(read_skill_trace "$events")"
  if [[ "$trace" == *"skill://slop-fix"* ]]; then
    printf 'FAIL read-only-boundary-slop-fix (fix skill handled a read-only review; artifacts: %s)\n' "$workdir" >&2
    return 1
  fi
  printf 'PASS read-only-boundary-slop-fix\n'
  rm -rf "$workdir"
}

validate_marketplace_install() {
  local workdir isolated_data skill plugin_list install_path events output trace

  workdir="$(mktemp -d "${TMPDIR:-/tmp}/slop-skills-omp-install.XXXXXX")"
  isolated_data="$workdir/data"
  plugin_list="$workdir/plugins.json"
  events="$workdir/events.jsonl"
  mkdir -p "$isolated_data/omp"
  printf 'RUN  marketplace-install\n'
  XDG_DATA_HOME="$isolated_data" "$OMP_BIN" plugin marketplace add "$REPO_ROOT" >/dev/null
  XDG_DATA_HOME="$isolated_data" "$OMP_BIN" plugin install slop-skills@slop-skills >/dev/null
  XDG_DATA_HOME="$isolated_data" "$OMP_BIN" plugin list --json >"$plugin_list"
  install_path="$(jq -r '
    .marketplace[]
    | select(.id == "slop-skills@slop-skills")
    | .entries[]
    | select(.scope == "user")
    | .installPath
  ' "$plugin_list")"
  [[ -d "$install_path" ]] ||
    fail "OMP did not register the installed plugin (artifacts: $workdir)"
  for skill in deslop slopmeter slop-fix slop-brief; do
    [[ -f "$install_path/skills/$skill/SKILL.md" ]] ||
      fail "installed plugin omitted $skill (artifacts: $workdir)"
  done

  XDG_DATA_HOME="$isolated_data" "$OMP_BIN" -p --mode json --no-session --no-title \
    --no-rules --max-time 2m --thinking high --tools read --skills slopmeter \
    '/skill:slopmeter Without using other tools, return only the exact clean-review sentence required by this skill.' \
    >"$events"
  output="$(extract_final_message "$events")"
  trace="$(read_skill_trace "$events")"
  [[ "$trace" == *"skill://slopmeter"* ]] ||
    fail "fresh OMP session did not discover the installed plugin (artifacts: $workdir)"
  [[ "$output" == "No open product-impacting findings." ]] ||
    fail "installed Slopmeter returned an unexpected contract answer (artifacts: $workdir)"

  printf 'PASS marketplace-install\n'
  rm -rf "$workdir"
}

command -v "$OMP_BIN" >/dev/null || fail "OMP CLI is required: $OMP_BIN"
command -v jq >/dev/null || fail "jq is required"
[[ -f "$REPO_ROOT/.omp-plugin/marketplace.json" ]] || fail "OMP marketplace catalog is missing"

validate_marketplace_install
run_probe deslop \
  'According to this skill, return only its four independent cleanup review angles in order, separated by comma and space.' \
  'reuse, simplification, efficiency, altitude'
run_probe slopmeter \
  'Without inspecting a repository, return only the exact sentence required when a fresh review has no supported open findings.' \
  'No open product-impacting findings.'
run_probe slop-fix \
  'According to this skill, complete this sentence with only the missing words: Judge scope by ___, not by ___.' \
  'behavior and necessity, file location'
run_probe slop-brief \
  'According to this skill, return only the two required section names after the opening product-change sentence, separated by comma and space.' \
  'Dictionary, Changes in logical order'

run_implicit_probe deslop \
  'Load the applicable specialized workflow for a behavior-preserving cleanup of a changed-code diff. Do not inspect files; return only its name.'
run_implicit_probe slopmeter \
  'Load the applicable specialized workflow for a harmless, strictly read-only pull-request defect review. Do not inspect files; return only its name.'
run_implicit_probe slop-brief \
  'Load the applicable specialized workflow for explaining a pull request in product language. Do not inspect files; return only its name.'
run_implicit_probe slop-fix \
  'Load the applicable specialized workflow for a direct request to fix verified P-level findings within a pull request. Do not inspect files; return only its name.'
run_read_only_boundary_probe

printf 'All OMP marketplace and fresh-session probes passed.\n'
