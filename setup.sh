#!/usr/bin/env bash
set -e

echo "=== Trump Trade Monitor — Setup ==="

# Python dependencies
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
cd ..

# Config
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo ""
  echo "✅  config.json created from example."
  echo "👉  Edit config.json with your API keys before running."
fi

echo ""
echo "=== Setup complete! ==="
echo "Next: edit config.json with your keys, then run:"
echo "  bash run.sh"
