#!/bin/bash
# Video Factory Kit - health check (Mac). In Terminal, inside the kit's folder:  bash check.sh
# Writes check_report.txt.
cd "$(dirname "$0")"
if [ -x tools/venv_render/bin/python ]; then
  tools/venv_render/bin/python tools/check.py
elif command -v python3.12 >/dev/null 2>&1; then
  python3.12 tools/check.py
else
  python3 tools/check.py
fi
