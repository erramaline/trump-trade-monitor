#!/usr/bin/env bash
set -e

if [ ! -f config.json ]; then
  echo "⚠  config.json not found. Running setup first..."
  bash setup.sh
fi

echo "🚀  Starting Trump Trade Monitor at http://localhost:8000"
uvicorn server:app --reload --host 0.0.0.0 --port 8000
