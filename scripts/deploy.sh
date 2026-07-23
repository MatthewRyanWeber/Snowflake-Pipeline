#!/usr/bin/env bash
#
# Phase 0 · Idempotent deploy of the Snowflake environment.
# Runs every sql/00_setup/*.sql in numeric order via SnowSQL.
#
# Credentials NEVER live in this repo — they come from a named connection in
# ~/.snowsql/config. Object names come from config/pipeline.conf.
#
# Usage:
#   scripts/deploy.sh [--connection NAME] [--config PATH] [--dry-run]
#
#   --dry-run      Print what would run (resolved command + SQL) without executing.
#   --connection   Override SF_CONNECTION from the config file.
#   --config       Path to the config file (default: config/pipeline.conf).
#
# Target shell: bash on WSL2 / Linux.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/config/pipeline.conf"
SETUP_DIR="$REPO_ROOT/sql/00_setup"
DRY_RUN=0
CONNECTION_OVERRIDE=""

log() { printf '%s [deploy] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

usage() { sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRY_RUN=1 ;;
    --connection)  CONNECTION_OVERRIDE="${2:-}"; shift ;;
    --config)      CONFIG_FILE="${2:-}"; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)             die "unknown argument: $1  (try --help)" ;;
  esac
  shift
done

[ -f "$CONFIG_FILE" ] || die "config not found: $CONFIG_FILE"
# shellcheck disable=SC1090
. "$CONFIG_FILE"

CONNECTION="${CONNECTION_OVERRIDE:-${SF_CONNECTION:-}}"
[ -n "$CONNECTION" ] || die "no connection set (SF_CONNECTION in config or --connection)"

for v in SF_ROLE SF_WAREHOUSE SF_WH_SIZE SF_WH_AUTO_SUSPEND \
         SF_DATABASE SF_SCHEMA_RAW SF_SCHEMA_STAGING SF_SCHEMA_MARTS; do
  [ -n "${!v:-}" ] || die "missing required config value: $v"
done

SNOWSQL_VARS=(
  -D "sf_role=$SF_ROLE"
  -D "sf_warehouse=$SF_WAREHOUSE"
  -D "sf_wh_size=$SF_WH_SIZE"
  -D "sf_wh_auto_suspend=$SF_WH_AUTO_SUSPEND"
  -D "sf_database=$SF_DATABASE"
  -D "sf_schema_raw=$SF_SCHEMA_RAW"
  -D "sf_schema_staging=$SF_SCHEMA_STAGING"
  -D "sf_schema_marts=$SF_SCHEMA_MARTS"
)

if [ "$DRY_RUN" -eq 0 ]; then
  command -v snowsql >/dev/null 2>&1 \
    || die "snowsql not found on PATH. Install SnowSQL and configure connection '$CONNECTION' in ~/.snowsql/config."
fi

shopt -s nullglob
files=("$SETUP_DIR"/*.sql)
shopt -u nullglob
[ "${#files[@]}" -gt 0 ] || die "no .sql files in $SETUP_DIR"
IFS=$'\n' files=($(sort <<<"${files[*]}")); unset IFS

log "connection : $CONNECTION"
log "database   : $SF_DATABASE  (schemas: $SF_SCHEMA_RAW, $SF_SCHEMA_STAGING, $SF_SCHEMA_MARTS)"
log "warehouse  : $SF_WAREHOUSE ($SF_WH_SIZE, auto-suspend ${SF_WH_AUTO_SUSPEND}s)"
log "role       : $SF_ROLE"
log "scripts    : ${#files[@]} file(s)"
[ "$DRY_RUN" -eq 1 ] && log "MODE       : DRY RUN (no execution)"

for f in "${files[@]}"; do
  log "--- $(basename "$f")"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] snowsql -c $CONNECTION ${SNOWSQL_VARS[*]} -f $f"
    continue
  fi
  # WHY: exit_on_error stops the whole deploy on the first failed statement (fail loud).
  snowsql -c "$CONNECTION" "${SNOWSQL_VARS[@]}" \
    -o exit_on_error=true -o friendly=false -o output_format=plain \
    -f "$f"
done

log "done."
