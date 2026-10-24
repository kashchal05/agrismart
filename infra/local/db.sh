#!/usr/bin/env bash
# Create the local Agrismart databases on the machine's running Postgres (port 5432).
#
# macOS 14 has no prebuilt PostGIS and building it needs full Xcode, so for local dev we
# store field geometry as JSONB on plain Postgres (see docs/adr/0001-geometry-storage.md).
# PostGIS comes online on AWS RDS (one-line enable) or any PostGIS-capable local DB later.
#
# Usage: infra/local/db.sh {create|drop}
set -euo pipefail

HOST="${AGRISMART_PGHOST:-localhost}"
PORT="${AGRISMART_PGPORT:-5432}"

create() {
  createdb -h "$HOST" -p "$PORT" agrismart 2>/dev/null && echo "created agrismart" \
    || echo "agrismart already exists"
  createdb -h "$HOST" -p "$PORT" agrismart_test 2>/dev/null && echo "created agrismart_test" \
    || echo "agrismart_test already exists"
}

drop() {
  dropdb -h "$HOST" -p "$PORT" --if-exists agrismart
  dropdb -h "$HOST" -p "$PORT" --if-exists agrismart_test
  echo "dropped agrismart databases"
}

case "${1:-}" in
  create) create ;; drop) drop ;;
  *) echo "usage: $0 {create|drop}"; exit 1 ;;
esac
