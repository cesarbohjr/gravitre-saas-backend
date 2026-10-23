#!/usr/bin/env bash
# Pinned extension installation for the disposable CI Supabase container only.
set -euo pipefail
source_dir="${1:?Provide the checked-out pgvector 0.8.0 source directory}"
test -f "$source_dir/vector.control"
grep -Eq "default_version[[:space:]]*=[[:space:]]*'0.8.0'" "$source_dir/vector.control"
docker cp "$source_dir" supabase_db_gravitre-operator-ai:/tmp/pgvector-0.8.0
docker exec --user root supabase_db_gravitre-operator-ai bash -ec '
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache build-base postgresql17-dev
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential postgresql-server-dev-17
  else
    echo "Unsupported PostgreSQL container package manager" >&2; exit 1
  fi
  command -v pg_config
  test "$(pg_config --version | cut -d " " -f2 | cut -d. -f1)" = 17
  cd /tmp/pgvector-0.8.0
  make PG_CONFIG="$(command -v pg_config)"
  make PG_CONFIG="$(command -v pg_config)" install
  sharedir="$(pg_config --sharedir)"
  control="$sharedir/extension/vector.control"
  test -f "$control" || { echo "pgvector control not installed at $control" >&2; exit 1; }
  sed -i -E "s/^default_version[[:space:]]*=.*/default_version = '\''0.8.0'\''/" "$control"
  grep -E "^default_version[[:space:]]*=[[:space:]]*'\''0.8.0'\''" "$control"
'
docker exec supabase_db_gravitre-operator-ai psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c 'DROP EXTENSION IF EXISTS vector CASCADE;'
docker exec supabase_db_gravitre-operator-ai psql -U supabase_admin -d postgres -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION vector WITH SCHEMA public VERSION '\''0.8.0'\'';'
docker exec supabase_db_gravitre-operator-ai psql -U postgres -d postgres -v ON_ERROR_STOP=1 -Atc "SELECT extversion FROM pg_extension WHERE extname='vector'" | grep -x 0.8.0
