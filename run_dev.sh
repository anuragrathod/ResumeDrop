#!/bin/bash
set -e

export PATH="/usr/local/bin:$PATH"

# Ensure dependencies from requirements.txt are installed
if ! python3 -c "import fastapi, uvicorn" &>/dev/null; then
    if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
        curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py --break-system-packages -q
    fi
    python3 -m pip install -q --no-warn-script-location --break-system-packages -r requirements.txt
fi

echo "Starting FastAPI server on port 3000..."
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 3000 --log-level info

