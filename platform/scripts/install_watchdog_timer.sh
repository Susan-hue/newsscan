#!/usr/bin/env bash
# Installs (or removes) the timer that runs stack_watchdog.py every minute.
# It is a user timer: no sudo, and it only touches ~/.config/systemd/user.
#
#   bash platform/scripts/install_watchdog_timer.sh            install and start
#   bash platform/scripts/install_watchdog_timer.sh --remove   stop and remove
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEST="$HOME/.config/systemd/user"

if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now newsscan-stack-watchdog.timer 2>/dev/null || true
  rm -f "$DEST/newsscan-stack-watchdog.service" "$DEST/newsscan-stack-watchdog.timer"
  systemctl --user daemon-reload
  echo "Removed."
  exit 0
fi

mkdir -p "$DEST"
sed "s|@REPO@|$REPO|" "$HERE/systemd/newsscan-stack-watchdog.service.in" > "$DEST/newsscan-stack-watchdog.service"
cp "$HERE/systemd/newsscan-stack-watchdog.timer" "$DEST/newsscan-stack-watchdog.timer"
systemctl --user daemon-reload
systemctl --user enable --now newsscan-stack-watchdog.timer
echo "Installed. Check it with: systemctl --user list-timers newsscan-stack-watchdog.timer"
