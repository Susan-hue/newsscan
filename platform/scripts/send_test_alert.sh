#!/usr/bin/env bash
# Sends a fake alert through Alertmanager so you can check that your phone gets it.
#
#   bash platform/scripts/send_test_alert.sh              a normal (warning) alert
#   bash platform/scripts/send_test_alert.sh critical     an urgent one: tests the loud, silent-mode-breaking path
#
# The alert ends by itself after 2 minutes, and you should then get a "Fixed" message too.
set -euo pipefail

SEVERITY="${1:-warning}"
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
END="$(date -u -d '+2 minutes' +%Y-%m-%dT%H:%M:%SZ)"

curl -sf -X POST http://127.0.0.1:9093/api/v2/alerts -H 'Content-Type: application/json' -d "[{
  \"labels\": {\"alertname\": \"TestAlert\", \"severity\": \"$SEVERITY\"},
  \"annotations\": {\"summary\": \"A test alert\", \"description\": \"This is only a test. Nothing is broken.\"},
  \"startsAt\": \"$START\", \"endsAt\": \"$END\"
}]" > /dev/null
echo "Sent a $SEVERITY test alert. It reaches your phone in about 10 to 30 seconds."
