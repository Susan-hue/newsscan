#!/usr/bin/env bash
# Runs every check in one go:  scripts/check.sh
# Needs the app's Python environment active:  cd app && source .venv/bin/activate && pip install -e ".[dev]"
# The Docker steps are skipped if Docker isn't running.

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=()

if ! python3 -m pytest --version >/dev/null 2>&1 || ! python3 -m ruff --version >/dev/null 2>&1; then
  echo "Missing pytest or ruff. Activate the app's environment first:"
  echo "  cd app && source .venv/bin/activate && pip install -e \".[dev]\""
  exit 2
fi

step() {  # step "name" command...   Prints ok or FAILED, and the end of the output if it failed.
  local name="$1"; shift
  printf '%-36s' "$name"
  if out=$("$@" 2>&1); then echo "ok"; else echo "FAILED"; echo "$out" | tail -12 | sed 's/^/    /'; FAILED+=("$name"); fi
}

skip() { printf '%-36s%s\n' "$1" "skipped ($2)"; }

alembic_check() {
  local dir rc
  dir=$(mktemp -d)
  cd "$ROOT/app" || return 1
  export NEWSSCAN_DATABASE_URL="sqlite:///$dir/check.db"   # a throwaway database, never your real one
  python3 -m alembic upgrade head >/dev/null && python3 -m alembic check
  rc=$?
  rm -rf "$dir"
  return $rc
}

no_tracked_env() {
  local tracked
  tracked=$(git -C "$ROOT" ls-files | grep -E '(^|/)\.env$')
  [ -z "$tracked" ] || { echo "A real .env file is tracked by Git: $tracked"; return 1; }
}

ports_on_localhost_only() {  # a published port must start with 127.0.0.1, so it never shows on the network
  local bad
  bad=$(grep -nE '^[[:space:]]*-[[:space:]]*"?[0-9]+:[0-9]+' "$ROOT/app/docker-compose.yml" "$ROOT/platform/docker-compose.yml")
  [ -z "$bad" ] || { echo "Port not bound to 127.0.0.1:"; echo "$bad"; return 1; }
}

containers_see_current_files() {  # git switch/merge can replace a folder, and a running container keeps the old one
  local running
  running=$(docker ps --format '{{.Names}}' | grep -E '^newsscan-platform-(prometheus|grafana)-1$')
  [ -n "$running" ] || { echo "not running"; return 0; }
  docker exec newsscan-platform-prometheus-1 cat /etc/prometheus/prometheus.yml \
    | cmp -s - "$ROOT/platform/prometheus/prometheus.yml" \
    || { echo "Prometheus sees an old prometheus.yml. Run: cd platform && docker compose up -d --force-recreate"; return 1; }
  docker exec newsscan-platform-grafana-1 sh -c 'ls /etc/grafana/dashboards/*.json' >/dev/null 2>&1 \
    || { echo "Grafana can't see the dashboards folder. Run: cd platform && docker compose up -d --force-recreate"; return 1; }
}

prometheus_config() {
  local image
  image=$(grep -oE 'prom/prometheus:[^ ]+' "$ROOT/platform/docker-compose.yml" | head -1)
  docker run --rm --entrypoint promtool -v "$ROOT/platform/prometheus:/etc/prometheus:ro" "$image" \
    check config /etc/prometheus/prometheus.yml
}

no_secret_values_in_files() {  # looks for the real values of your keys and passwords in any file Git could commit
  local patterns hits
  patterns=$(mktemp)
  chmod 600 "$patterns"
  # values of KEY, PASSWORD, TOKEN and SECRET lines in the ignored .env files, plus the ntfy topic
  grep -hE '^[A-Za-z_]*(KEY|PASSWORD|TOKEN|SECRET)[A-Za-z_]*=' "$ROOT/app/.env" "$ROOT/platform/.env" 2>/dev/null \
    | cut -d= -f2- | awk 'length($0) >= 8' > "$patterns"
  [ -s "$ROOT/platform/secrets/ntfy_topic" ] && tr -d '\n' < "$ROOT/platform/secrets/ntfy_topic" >> "$patterns" && echo >> "$patterns"
  if [ ! -s "$patterns" ]; then rm -f "$patterns"; echo "no secrets found to look for"; return 0; fi
  # tracked files and new files that are not ignored; only file names are printed, never the values
  hits=$(cd "$ROOT" && git ls-files -co --exclude-standard -z | xargs -0 grep -lIF -f "$patterns" 2>/dev/null)
  rm -f "$patterns"
  [ -z "$hits" ] || { echo "A real secret value appears in these files (not printing it):"; echo "$hits"; return 1; }
}

alert_rule_tests() {  # the alert rules are tested with fake data, so a rule that never fires can't hide
  local image
  image=$(grep -oE 'prom/prometheus:[^ ]+' "$ROOT/platform/docker-compose.yml" | head -1)
  docker run --rm --entrypoint promtool -v "$ROOT/platform/prometheus:/etc/prometheus:ro" "$image" \
    test rules /etc/prometheus/tests/alerts_test.yml
}

alertmanager_config() {  # the real secret files are not needed: it is checked with dummy ones
  local image tmp
  image=$(grep -oE 'prom/alertmanager:[^ ]+' "$ROOT/platform/docker-compose.yml" | head -1)
  tmp=$(mktemp -d)
  chmod 755 "$tmp"
  echo "https://example.com/x" | tee "$tmp/ntfy_critical_url" "$tmp/ntfy_warning_url" >/dev/null
  chmod 644 "$tmp"/ntfy_*_url
  docker run --rm --entrypoint amtool -v "$ROOT/platform/alertmanager:/etc/alertmanager:ro" -v "$tmp:/secrets:ro" "$image" \
    check-config /etc/alertmanager/alertmanager.yml
  local result=$?
  rm -rf "$tmp"
  return $result
}

step "App tests"                 bash -c "cd '$ROOT/app' && python3 -m pytest -q -p no:cacheprovider"
step "Platform script tests"     bash -c "cd '$ROOT/platform' && python3 -m pytest -q -p no:cacheprovider tests"
step "Lint and format"           bash -c "cd '$ROOT/app' && python3 -m ruff check --config pyproject.toml . ../platform && python3 -m ruff format --check --config pyproject.toml . ../platform"
step "Database migrations match"  alembic_check
step "Dashboard file up to date" bash -c "cd '$ROOT/platform' && python3 grafana/make_dashboard.py --check"
step "No .env tracked by Git"    no_tracked_env
step "No secret values in files" no_secret_values_in_files
step "Ports bound to 127.0.0.1"  ports_on_localhost_only

if docker info >/dev/null 2>&1; then
  step "App compose file"        bash -c "cd '$ROOT/app' && POSTGRES_PASSWORD=check docker compose config -q"
  step "Platform compose file"   bash -c "cd '$ROOT/platform' && GRAFANA_ADMIN_PASSWORD=check POSTGRES_EXPORTER_PASSWORD=check docker compose config -q"
  step "Prometheus config"       prometheus_config
  step "Alert rule tests"        alert_rule_tests
  step "Alertmanager config"     alertmanager_config
  step "Containers see current files" containers_see_current_files
else
  skip "App compose file" "Docker is not running"
  skip "Platform compose file" "Docker is not running"
  skip "Prometheus config" "Docker is not running"
  skip "Alert rule tests" "Docker is not running"
  skip "Alertmanager config" "Docker is not running"
  skip "Containers see current files" "Docker is not running"
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then echo "All checks passed."; else echo "${#FAILED[@]} failed: ${FAILED[*]}"; exit 1; fi
