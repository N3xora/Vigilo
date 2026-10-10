#!/usr/bin/env bash
# Stop the API and scanner worker started by scripts/e2e-up.sh.
pkill -f "uvicorn vigilo_api.main:app --port 8000" 2>/dev/null || true
pkill -f "arq vigilo_scanner.worker.WorkerSettings" 2>/dev/null || true
exit 0
