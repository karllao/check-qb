#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m check_qb.cli serve "$@"
fi
exec python3 -m check_qb.cli serve "$@"
