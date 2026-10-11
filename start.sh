#!/bin/bash
set -e

echo "Starting CommerceIQ FastAPI Backend..."
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "Waiting for API to start..."
while ! python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; do
    sleep 1
done

echo "FastAPI is healthy. Starting Streamlit Dashboard..."
PORT="${PORT:-8501}"
python -m streamlit run dashboard/app.py --server.port "${PORT}" --server.address 0.0.0.0 --server.headless true

wait $API_PID
