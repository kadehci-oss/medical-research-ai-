#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

python - <<'PY'
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit("Select Python 3.12 in the Codex environment settings.")
PY

python -m pip install -r requirements.lock
python -m pip check
