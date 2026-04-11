#!/usr/bin/env bash
# run_gold.sh — Gold Tier Entry Point Script
#
# Runs the Gold Tier autonomous loop with optional modes.
#
# Usage:
#   ./run_gold.sh              # continuous gold loop (default)
#   ./run_gold.sh --once       # single cycle then exit
#   ./run_gold.sh --watchers   # run watchers only (single scan)
#   ./run_gold.sh --loop       # run reasoning loop only (single cycle)
#   ./run_gold.sh --report     # generate CEO report now
#   ./run_gold.sh --audit      # run business audit now
#   ./run_gold.sh --dry-run    # analyze only, no execution

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOG_FILE="${VAULT_DIR}/watcher.log"

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    local msg="$(timestamp) : [gold-scheduler] $1"
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
# Gold loop
# ---------------------------------------------------------------------------
run_gold_loop() {
    local extra_args="${1:-}"
    log "starting Gold Tier loop"
    "$PYTHON" "${VAULT_DIR}/gold_loop.py" $extra_args 2>&1 | tee -a "$LOG_FILE"
    log "Gold Tier loop complete"
}

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
run_report() {
    log "generating CEO weekly report"
    "$PYTHON" "${VAULT_DIR}/ceo_report_generator.py" 2>&1 | tee -a "$LOG_FILE"
    log "CEO report generation complete"
}

run_audit() {
    log "running business audit"
    "$PYTHON" "${VAULT_DIR}/business_audit.py" 2>&1 | tee -a "$LOG_FILE"
    log "business audit complete"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log "=== Gold Tier Run Started ==="

    case "${1:-continuous}" in
        --once)
            run_gold_loop "--once"
            ;;
        --watchers)
            run_watchers
            ;;
        --loop)
            run_gold_loop "--once"
            ;;
        --report)
            run_report
            ;;
        --audit)
            run_audit
            ;;
        --dry-run)
            run_gold_loop "--dry-run"
            ;;
        continuous|*)
            run_gold_loop
            ;;
    esac

    log "=== Gold Tier Run Complete ==="
}

main "$@"
