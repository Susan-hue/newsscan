#!/usr/bin/env bash
# Installs (or removes) the timer that runs docker_stats.py every 15 seconds.
# It is a user timer: no sudo, and it only touches ~/.config/systemd/user.
#
#   bash platform/scripts/install_docker_stats_timer.sh            install and start
#   bash platform/scripts/install_docker_stats_timer.sh --remove   stop and remove
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEST="$HOME/.config/systemd/user"

if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now newsscan-docker-stats.timer 2>/dev/null || true
  rm -f "$DEST/newsscan-docker-stats.service" "$DEST/newsscan-docker-stats.timer"
  systemctl --user daemon-reload
  echo "Removed. The file platform/textfile/docker_containers.prom is left in place."
  exit 0
fi

mkdir -p "$DEST"
sed "s|@REPO@|$REPO|" "$HERE/systemd/newsscan-docker-stats.service.in" > "$DEST/newsscan-docker-stats.service"
cp "$HERE/systemd/newsscan-docker-stats.timer" "$DEST/newsscan-docker-stats.timer"
systemctl --user daemon-reload
systemctl --user enable --now newsscan-docker-stats.timer
echo "Installed. Check it with: systemctl --user list-timers newsscan-docker-stats.timer"
