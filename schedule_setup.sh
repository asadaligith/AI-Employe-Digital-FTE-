#!/usr/bin/env bash
# schedule_setup.sh — Install Silver Tier Scheduling
#
# Sets up a daily cron job (Linux/macOS) or Task Scheduler entry (WSL/Windows)
# to run the Silver Tier pipeline automatically.
#
# Usage:
#   ./schedule_setup.sh              # auto-detect and install
#   ./schedule_setup.sh --cron       # force cron setup
#   ./schedule_setup.sh --remove     # remove scheduled job
#   ./schedule_setup.sh --status     # show current schedule

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_SCRIPT="${VAULT_DIR}/run_silver.sh"
CRON_TAG="# silver-tier-daily"
HOUR="${SILVER_RUN_HOUR:-8}"  # Default: 8:00 UTC

log() {
    echo "[schedule] $1"
}

# ---------------------------------------------------------------------------
# Cron-based scheduling (Linux/macOS/WSL)
# ---------------------------------------------------------------------------
install_cron() {
    # Check if already installed
    if crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
        log "cron job already installed:"
        crontab -l | grep "$CRON_TAG"
        return 0
    fi

    # Add cron entry
    local cron_line="0 ${HOUR} * * * /usr/bin/env bash ${RUN_SCRIPT} >> ${VAULT_DIR}/watcher.log 2>&1 ${CRON_TAG}"

    (crontab -l 2>/dev/null || true; echo "$cron_line") | crontab -

    log "cron job installed: daily at ${HOUR}:00 UTC"
    log "entry: $cron_line"
    log ""
    log "verify with: crontab -l | grep silver"
}

remove_cron() {
    if ! crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
        log "no cron job found to remove"
        return 0
    fi

    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    log "cron job removed"
}

show_status() {
    log "checking for Silver Tier scheduled jobs..."
    echo ""

    # Check cron
    if crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
        echo "CRON:"
        crontab -l | grep "$CRON_TAG"
    else
        echo "CRON: not installed"
    fi

    echo ""

    # Check if WSL, show Windows Task Scheduler guidance
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "WSL DETECTED — For Windows Task Scheduler:"
        echo "  1. Open Task Scheduler (taskschd.msc)"
        echo "  2. Create Basic Task: 'Silver Tier Daily'"
        echo "  3. Trigger: Daily at ${HOUR}:00"
        echo "  4. Action: Start a program"
        echo "     Program: wsl"
        echo "     Arguments: bash ${RUN_SCRIPT}"
        echo ""
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Make run script executable
chmod +x "$RUN_SCRIPT" 2>/dev/null || true

case "${1:-install}" in
    --cron|install)
        install_cron
        ;;
    --remove)
        remove_cron
        ;;
    --status)
        show_status
        ;;
    *)
        echo "Usage: $0 [--cron|--remove|--status]"
        echo ""
        echo "  --cron    Install daily cron job (default)"
        echo "  --remove  Remove the cron job"
        echo "  --status  Show current scheduling status"
        exit 1
        ;;
esac
