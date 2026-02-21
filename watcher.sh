#!/usr/bin/env bash
#
# watcher.sh — Filesystem watcher for AI Employee Vault
#
# Usage:
#   chmod +x watcher.sh
#   ./watcher.sh &          # run in background
#   kill %1                 # stop when done
#
# Prefers inotifywait (inotify-tools) for event-driven watching.
# Falls back to polling (2s interval) if inotify-tools is not installed.
#
# Monitors the Needs_Action/ directory for newly created .md files
# and logs each event (ISO timestamp + filename) to watcher.log
# in the vault root.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCH_DIR="${SCRIPT_DIR}/Needs_Action"
LOG_FILE="${SCRIPT_DIR}/watcher.log"

if [ ! -d "$WATCH_DIR" ]; then
    echo "ERROR: Watch directory not found: $WATCH_DIR" >&2
    exit 1
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) : watcher started — monitoring ${WATCH_DIR}" | tee -a "$LOG_FILE"

if command -v inotifywait &>/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) : mode — inotifywait (event-driven)" | tee -a "$LOG_FILE"
    while true; do
        filename=$(inotifywait -q -e create --format '%f' "$WATCH_DIR")
        if [[ "$filename" == *.md ]]; then
            timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
            echo "${timestamp} : new file detected — ${filename}" | tee -a "$LOG_FILE"
        fi
    done
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) : mode — polling (2s interval, inotifywait not found)" | tee -a "$LOG_FILE"
    declare -A KNOWN_FILES
    # Seed with existing files
    for f in "$WATCH_DIR"/*.md; do
        [ -e "$f" ] && KNOWN_FILES["$(basename "$f")"]=1
    done
    while true; do
        for f in "$WATCH_DIR"/*.md; do
            [ -e "$f" ] || continue
            base="$(basename "$f")"
            if [ -z "${KNOWN_FILES[$base]+_}" ]; then
                KNOWN_FILES["$base"]=1
                timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
                echo "${timestamp} : new file detected — ${base}" | tee -a "$LOG_FILE"
            fi
        done
        sleep 2
    done
fi
