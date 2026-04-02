#!/bin/sh

set -eu

APP_MODULE="${BACKEND_APP_MODULE:-main:app}"
HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
LOG_LEVEL="${BACKEND_LOG_LEVEL:-debug}"
RELOAD="${BACKEND_RELOAD:-true}"
DEBUGPY_ENABLED="${BACKEND_DEBUGPY:-false}"
DEBUGPY_HOST="${BACKEND_DEBUGPY_HOST:-0.0.0.0}"
DEBUGPY_PORT="${BACKEND_DEBUGPY_PORT:-5678}"
DEBUGPY_WAIT="${BACKEND_DEBUGPY_WAIT_FOR_CLIENT:-false}"

set -- uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"

if [ "$RELOAD" = "true" ]; then
  set -- "$@" --reload
fi

if [ "$DEBUGPY_ENABLED" = "true" ]; then
  echo "Starting backend with debugpy on ${DEBUGPY_HOST}:${DEBUGPY_PORT}"

  if [ "$DEBUGPY_WAIT" = "true" ]; then
    exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --wait-for-client -m "$@"
  fi

  exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" -m "$@"
fi

exec "$@"
