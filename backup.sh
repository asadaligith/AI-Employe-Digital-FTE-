#!/usr/bin/env bash
#
# backup.sh — Vault backup utility for AI Employee Vault
#
# Usage:
#   chmod +x backup.sh
#   ./backup.sh
#
# Archives Dashboard.md, Company_Handbook.md, Done/, and watcher.log
# into a timestamped .tar.gz inside the Backups/ directory.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/Backups"
TIMESTAMP=$(date -u +%Y-%m-%dT%H-%M-%SZ)
ARCHIVE_NAME="vault-backup-${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

# Collect files to archive (relative paths from vault root)
FILES=()
cd "$SCRIPT_DIR" || exit 1

for target in Dashboard.md Company_Handbook.md Done/; do
    [ -e "$target" ] && FILES+=("$target")
done
[ -f watcher.log ] && FILES+=(watcher.log)

if [ ${#FILES[@]} -eq 0 ]; then
    echo "ERROR: No files found to back up." >&2
    exit 1
fi

tar -czf "${BACKUP_DIR}/${ARCHIVE_NAME}" "${FILES[@]}"

SIZE=$(du -h "${BACKUP_DIR}/${ARCHIVE_NAME}" | cut -f1)
echo "Backup complete: ${ARCHIVE_NAME} (${SIZE})"
