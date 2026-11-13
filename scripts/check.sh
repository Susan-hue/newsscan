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

step "App tests"                 bash -c "cd '$ROOT/app' && python3 -m pytest -q -p no:cacheprovider"
step "Lint and format"           bash -c "cd '$ROOT/app' && python3 -m ruff check . && python3 -m ruff format --check ."
step "Database migrations match"  alembic_check
step "Dashboard file up to date" bash -c "cd '$ROOT/platform' && python3 grafana/make_dashboard.py --check"
step "No .env tracked by Git"    no_tracked_env
step "Ports bound to 127.0.0.1"  ports_on_localhost_only

if docker info >/dev/null 2>&1; then
  step "App compose file"        bash -c "cd '$ROOT/app' && POSTGRES_PASSWORD=check docker compose config -q"
  step "Platform compose file"   bash -c "cd '$ROOT/platform' && GRAFANA_ADMIN_PASSWORD=check docker compose config -q"
  step "Prometheus config"       prometheus_config
  step "Containers see current files" containers_see_current_files
else
  skip "App compose file" "Docker is not running"
  skip "Platform compose file" "Docker is not running"
  skip "Prometheus config" "Docker is not running"
  skip "Containers see current files" "Docker is not running"
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then echo "All checks passed."; else echo "${#FAILED[@]} failed: ${FAILED[*]}"; exit 1; fi
