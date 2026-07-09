#!/usr/bin/bash
# Audit canfar-lab help text vs accepted flags. Exit 1 on mismatches.
set -euo pipefail
cd "$(dirname "$0")/.."
CLI=(uv run canfar-lab)
FAIL=0

check_help_ok() {
    local label="$1"
    shift
    if "${CLI[@]}" "$@" --help >/dev/null 2>&1; then
        echo "  ok  help: $label"
    else
        echo "  FAIL help: $label ($*)" >&2
        FAIL=$((FAIL + 1))
    fi
}

check_flag_in_help() {
    local label="$1"
    local flag="$2"
    shift 2
    local out
    out=$("${CLI[@]}" "$@" --help 2>&1) || true
    if grep -qF -- "$flag" <<< "$out"; then
        echo "  ok  flag $flag in $label"
    else
        echo "  FAIL missing flag $flag in $label" >&2
        FAIL=$((FAIL + 1))
    fi
}

check_invocation() {
    local label="$1"
    shift
    if "${CLI[@]}" "$@" >/dev/null 2>&1; then
        echo "  ok  run: $label"
    else
        local code=$?
        echo "  FAIL run ($code): $label ($*)" >&2
        FAIL=$((FAIL + 1))
    fi
}

check_help_accepts_flag() {
    local label="$1"
    local flag="$2"
    shift 2
    if "${CLI[@]}" "$@" "$flag" --help >/dev/null 2>&1; then
        echo "  ok  $label accepts $flag (subcommand placement)"
    else
        echo "  FAIL $label rejects $flag after subcommand" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Top-level ==="
if "${CLI[@]}" --help >/dev/null 2>&1; then
    echo "  ok  help: main"
else
    echo "  FAIL help: main" >&2
    FAIL=$((FAIL + 1))
fi
check_help_ok "guide" guide
check_help_ok "init" init
check_help_ok "clone" clone
check_help_ok "save" save
check_help_ok "resume" resume
check_help_ok "saves" saves
check_help_ok "push" push
check_help_ok "status" status
check_help_ok "paths" paths
check_help_ok "tools" tools
check_help_ok "check" check
check_help_ok "doctor" doctor

echo "=== Nested typers ==="
for grp in env data clean config workspace agent project kernel; do
    check_help_ok "$grp" "$grp"
done

echo "=== Global flags in main help ==="
MAIN=$("${CLI[@]}" --help 2>&1)
for flag in "--json" "--yes" "--dry-run" "--quiet" "--version"; do
    if grep -qF -- "$flag" <<< "$MAIN"; then
        echo "  ok  global $flag"
    else
        echo "  FAIL global $flag missing from main --help" >&2
        FAIL=$((FAIL + 1))
    fi
done

echo "=== Documented subcommand flags ==="
check_flag_in_help "clean home" "--dry-run" clean home
check_flag_in_help "clean home" "--all-safe" clean home
check_flag_in_help "clean cache" "--dry-run" clean cache
check_flag_in_help "data stage" "--dry-run" data stage
check_flag_in_help "data sync" "--yes" data sync
check_flag_in_help "init" "--uv" init
check_flag_in_help "clone" "--from-env" clone
check_flag_in_help "save" "--full" save
check_flag_in_help "resume" "--from" resume
check_flag_in_help "saves" "--json" saves
check_flag_in_help "status" "--json" status
check_flag_in_help "paths" "--json" paths
check_flag_in_help "tools" "--json" tools
check_flag_in_help "check" "--json" check
check_flag_in_help "check" "--strict" check
check_flag_in_help "push" "--yes" push
check_flag_in_help "doctor" "--json" doctor
check_flag_in_help "env list" "--json" env list
check_flag_in_help "kernel list" "--json" kernel list
check_flag_in_help "agent install" "--list" agent install
check_flag_in_help "agent models" "--preset" agent models free

echo "=== Flag placement (global OR subcommand) ==="
for spec in \
    "saves --json" \
    "status --json" \
    "paths --json" \
    "tools --json" \
    "check --json" \
    "push --yes" \
    "clean home --dry-run" \
    "clean cache --dry-run" \
    "data stage --dry-run" \
    "env list --json" \
    "kernel list --json"; do
    read -r -a parts <<< "$spec"
    check_help_accepts_flag "$spec" "${parts[-1]}" "${parts[@]:0:${#parts[@]}-1}"
done

echo "=== Smoke invocations (lab env) ==="
export HOME="/tmp/canfar-lab-audit-$$"
export CANFAR_LAB_WORK_DIR="$HOME/work"
export CANFAR_LAB_SCRATCH_DIR="$HOME/scratch"
mkdir -p "$HOME/work" "$HOME/scratch"
trap 'rm -rf "$HOME"' EXIT

check_invocation "guide" guide
check_invocation "status" status
check_invocation "status json sub" status --json
check_invocation "status json global" --json status
check_invocation "paths" paths
check_invocation "paths json" paths --json
check_invocation "tools" tools
check_invocation "tools json" tools --json
check_invocation "check" check
check_invocation "check json" check --json
check_invocation "doctor" doctor
check_invocation "saves list" saves
check_invocation "saves json sub" saves --json
check_invocation "config show" config show
check_invocation "config path" config path
check_invocation "env export" env export
check_invocation "env list" env list
check_invocation "env list json" env list --json
check_invocation "agent install list" agent install --list
check_invocation "agent models list" agent models
check_invocation "clean home dry-run sub" clean home --all-safe --dry-run
check_invocation "clean home dry-run global" --dry-run clean home --all-safe
check_invocation "clean cache dry-run" clean cache --all-safe --dry-run

echo ""
if [[ "$FAIL" -eq 0 ]]; then
    echo "CLI audit passed."
    exit 0
fi
echo "$FAIL audit failure(s)." >&2
exit 1
