#!/usr/bin/env bash
# Makes the secret address that Alertmanager sends phone alerts to, using ntfy.sh.
#
# On ntfy.sh, the topic name works like a password: anyone who knows it can read and send to it.
# So this makes a long random one, keeps it in platform/secrets/ (Git ignores that folder) and does not print it.
# Safe to run again: it keeps the same topic. Delete platform/secrets/ntfy_topic first to get a new one.
#
#   bash platform/scripts/setup_ntfy.sh
#   cat platform/secrets/ntfy_topic        <- the name to subscribe to in the ntfy app
set -euo pipefail

SECRETS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/secrets"
SERVER="https://ntfy.sh"
mkdir -p "$SECRETS"
chmod 711 "$SECRETS"   # the Alertmanager container runs as another user and must be able to pass through
umask 077

if [ ! -s "$SECRETS/ntfy_topic" ]; then
  printf 'newsscan-%s\n' "$(openssl rand -hex 12)" > "$SECRETS/ntfy_topic"
fi
TOPIC="$(tr -d '\n' < "$SECRETS/ntfy_topic")"

# ntfy turns Alertmanager's message into a readable one using this template.
# Critical alerts use priority 5 (urgent). Warnings use priority 3 (normal).
python3 - "$SERVER" "$TOPIC" "$SECRETS" <<'PY'
import sys, urllib.parse
server, topic, secrets = sys.argv[1:4]
title = '{{if eq .status "resolved"}}Fixed{{else}}PROBLEM{{end}}: {{.commonLabels.alertname}}'
message = '{{range .alerts}}{{.annotations.description}}\n{{end}}'
for name, priority, tags in (("critical", 5, "rotating_light"), ("warning", 3, "warning")):
    query = urllib.parse.urlencode(
        {"template": "yes", "title": title, "message": message, "priority": priority, "tags": tags},
        quote_via=urllib.parse.quote,
    )
    with open(f"{secrets}/ntfy_{name}_url", "w") as handle:
        handle.write(f"{server}/{topic}?{query}")
PY
chmod 644 "$SECRETS"/ntfy_critical_url "$SECRETS"/ntfy_warning_url   # the Alertmanager container reads these
echo "Done. Next: open the ntfy app and subscribe to the topic in platform/secrets/ntfy_topic"
