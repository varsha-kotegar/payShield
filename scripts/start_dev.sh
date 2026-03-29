#!/bin/bash
# Development server with auto-reload
cd "$(dirname "$0")/.."
python3 seed_demo.py 2>/dev/null || true
python3 app.py
