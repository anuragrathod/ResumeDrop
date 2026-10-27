#!/bin/bash
set -e

# If streamlit is not installed, install it from requirements.txt
if ! python3 -c "import streamlit" &>/dev/null; then
    if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
        curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py --break-system-packages
    fi
    pip install --break-system-packages -r requirements.txt
fi

echo "Starting Streamlit dev server on port 3000..."
exec streamlit run app.py --server.port 3000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false
