#!/usr/bin/env bash
# Scans every Docker image this project runs for known security problems that already have a fix.
# It uses Trivy (run in Docker, so nothing to install). The images are saved to a file first, so the scanner
# never gets your Docker socket. It needs internet, and takes a few minutes. It changes nothing.
#
#   bash scripts/scan_images.sh
#
# Run it now and then, and after changing an image version. A finding with a "fixed in" version means:
# a newer image or package fixes it. Findings inside tools we only run (Go libraries in Prometheus,
# for example) go away when you move to that tool's newer release.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIVY="aquasec/trivy:0.67.2"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

docker pull -q "$TRIVY" >/dev/null
# the image names: from both compose files, plus the app's own build
images=$( (grep -hoE '^\s+image:\s+\S+' "$ROOT/app/docker-compose.yml" "$ROOT/platform/docker-compose.yml" \
           | awk '{print $2}') | sort -u)

for image in $images; do
  if ! docker save "$image" -o "$WORK/image.tar" 2>/dev/null; then
    echo "$image: could not be saved for scanning (skipped)"; continue
  fi
  docker run --rm -v "$WORK:/in:ro" -v "$HOME/.cache/trivy-newsscan:/root/.cache" "$TRIVY" image \
    --input /in/image.tar --severity HIGH,CRITICAL --ignore-unfixed --quiet --format json 2>/dev/null \
    | python3 -c '
import json, sys
image = sys.argv[1]
try:
    data = json.load(sys.stdin)
except ValueError:
    print(f"{image}: scan failed (skipped)"); sys.exit(0)
found = {}
for result in data.get("Results", []):
    for v in result.get("Vulnerabilities") or []:
        found.setdefault((v["PkgName"], v["InstalledVersion"], v.get("FixedVersion", "")), set()).add(v["VulnerabilityID"])
if not found:
    print(f"{image}: clean (no fixable HIGH or CRITICAL)")
else:
    print(f"{image}: {sum(len(ids) for ids in found.values())} fixable HIGH or CRITICAL")
    for (pkg, ver, fix), ids in sorted(found.items())[:5]:
        print(f"    {pkg} {ver} -> fixed in {fix}: {sorted(ids)[0]}{\" ...\" if len(ids) > 1 else \"\"}")
' "$image"
done
