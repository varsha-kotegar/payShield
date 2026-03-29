#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  PayShield — Production startup script
#  Usage: chmod +x scripts/start.sh && ./scripts/start.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")/.."

echo "🛡  Starting PayShield..."

# Load environment
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Run DB migrations if needed
python3 -c "from db import init_db; init_db(); print('✅ DB ready')"

# Gunicorn: 4 workers, 2 threads each, 120s timeout
# Adjust --workers based on: (2 × CPU cores) + 1
exec gunicorn app:app \
  --workers        4 \
  --threads        2 \
  --worker-class   gthread \
  --timeout        120 \
  --bind           127.0.0.1:5000 \
  --access-logfile logs/access.log \
  --error-logfile  logs/error.log \
  --log-level      info \
  --pid            /tmp/payshield.pid \
  --capture-output
