#!/bin/sh
# Start script for the Django backend.
# Uses the active Python interpreter to run Django migrations and uvicorn.

set -eu

HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
LOG_LEVEL="${BACKEND_LOG_LEVEL:-debug}"
RELOAD="${BACKEND_RELOAD:-true}"
DEBUGPY_ENABLED="${BACKEND_DEBUGPY:-false}"
DEBUGPY_HOST="${BACKEND_DEBUGPY_HOST:-0.0.0.0}"
DEBUGPY_PORT="${BACKEND_DEBUGPY_PORT:-5678}"
DEBUGPY_WAIT="${BACKEND_DEBUGPY_WAIT_FOR_CLIENT:-false}"
DEBUGPY_SUBPROCESS="${BACKEND_DEBUGPY_SUBPROCESS:-false}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "Python interpreter not found. Set PYTHON_BIN or install python/python3." >&2
    exit 127
  fi
fi

# Apply any pending migrations before starting (safe to run on every boot)
echo "Running Django migrations..."
"$PYTHON_BIN" manage.py migrate --noinput

# Use uvicorn + Django ASGI for SSE streaming support
set -- "$PYTHON_BIN" -m uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"
UVICORN_RELOAD_ARG=""

if [ "$RELOAD" = "true" ]; then
  UVICORN_RELOAD_ARG="--reload"
  set -- "$@" --reload
fi

if [ "$DEBUGPY_ENABLED" = "true" ]; then
  echo "Starting backend with debugpy on ${DEBUGPY_HOST}:${DEBUGPY_PORT}"

  if [ "$DEBUGPY_WAIT" = "true" ]; then
    if [ "$DEBUGPY_SUBPROCESS" = "false" ]; then
      exec "$PYTHON_BIN" -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --configure-subProcess false --wait-for-client -m uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" $UVICORN_RELOAD_ARG
    fi
    exec "$PYTHON_BIN" -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --wait-for-client -m uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" $UVICORN_RELOAD_ARG
  fi

  if [ "$DEBUGPY_SUBPROCESS" = "false" ]; then
    exec "$PYTHON_BIN" -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --configure-subProcess false -m uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" $UVICORN_RELOAD_ARG
  fi

  exec "$PYTHON_BIN" -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" -m uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL" $UVICORN_RELOAD_ARG
fi

exec "$@"
