#!/usr/bin/env bash
# Makes a read-only Postgres login called "monitor" for the Postgres exporter.
# It can read Postgres's own statistics (the pg_monitor role). It cannot read your scan tables.
# Safe to run again: it keeps the same password and fixes the role if it already exists.
# The password is written to platform/.env (Git ignores it) and is never printed.
#
# Run it with the app running:   bash platform/scripts/create_postgres_monitor_role.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/../.env"
APP_COMPOSE="$HERE/../../app/docker-compose.yml"

touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
if ! grep -q '^POSTGRES_EXPORTER_PASSWORD=' "$ENV_FILE"; then
  printf 'POSTGRES_EXPORTER_PASSWORD=%s\n' "$(openssl rand -hex 16)" >> "$ENV_FILE"
fi
PW="$(grep '^POSTGRES_EXPORTER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

# The password goes in through stdin, not as a command-line argument, so it doesn't show in `ps`.
docker compose -f "$APP_COMPOSE" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' >/dev/null <<SQL
DO \$body\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'monitor') THEN
    CREATE ROLE monitor LOGIN;
  END IF;
END
\$body\$;
ALTER ROLE monitor WITH LOGIN PASSWORD '$PW' CONNECTION LIMIT 5;
GRANT pg_monitor TO monitor;
SQL
echo "The monitor role is ready."
