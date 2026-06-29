#!/usr/bin/env bash
#
# Cortex MLOps Backbone - one-command launcher
#
# Usage:
#   ./start.sh            Start the full stack (Docker Compose)
#   ./start.sh --down     Stop the stack
#   ./start.sh --down-v   Stop and wipe volumes
#   ./start.sh --logs     Tail logs
#
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

case "${1:-up}" in
  --down)   docker compose down ;;
  --down-v) docker compose down -v ;;
  --logs)   docker compose logs -f ;;
  up|*)
    echo "Starting Cortex MLOps Backbone..."
    docker compose up -d --build
    cat <<'MSG'

  Cortex is starting. Services:
    Feature Store:    http://localhost:8001/docs
    Model Registry:   http://localhost:8002/docs
    Serving:          http://localhost:8003/docs
    Drift Detection:  http://localhost:8004/docs
    Scheduler:        http://localhost:8005/docs
    Prometheus:       http://localhost:9090
    Grafana:          http://localhost:3000

  Tail logs:  ./start.sh --logs
  Stop:       ./start.sh --down
MSG
    ;;
esac
