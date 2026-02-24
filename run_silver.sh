#!/usr/bin/env bash
# run_silver.sh — Silver Tier Daily Execution Entry Point
#
# This script runs the complete Silver Tier pipeline:
#   1. Starts watchers for a single scan (--once)
#   2. Runs the reasoning loop (silver_loop.py)
#
# Usage:
#   ./run_silver.sh              # full daily run
#   ./run_silver.sh --watchers   # run watchers only
#   ./run_silver.sh --loop       # run reasoning loop only
#   ./run_silver.sh --dry-run    # analyze without executing

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_FILE="${VAULT_DIR}/watcher.log"

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    local msg="$(timestamp) : [scheduler] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Watcher scan
# ---------------------------------------------------------------------------
run_watchers() {
    log "starting watcher scan (single pass)"
    "$PYTHON" "${VAULT_DIR}/watcher_manager.py" --once 2>&1 | tee -a "$LOG_FILE"
    log "watcher scan complete"
}

# ---------------------------------------------------------------------------
# Reasoning loop
# ---------------------------------------------------------------------------
run_loop() {
    local extra_args=""
    if [[ "${1:-}" == "--dry-run" ]]; then
        extra_args="--dry-run"
    fi
    log "starting Silver Tier reasoning loop"
    "$PYTHON" "${VAULT_DIR}/silver_loop.py" $extra_args 2>&1 | tee -a "$LOG_FILE"
    log "reasoning loop complete"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log "=== Silver Tier Daily Run Started ==="

    case "${1:-full}" in
        --watchers)
            run_watchers
            ;;
        --loop)
            run_loop "${2:-}"
            ;;
        --dry-run)
            run_watchers
            run_loop "--dry-run"
            ;;
        full|*)
            run_watchers
            run_loop
            ;;
    esac

    log "=== Silver Tier Daily Run Complete ==="
}

main "$@"
