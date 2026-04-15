#!/bin/sh
# Start script for the Django backend.
# Mirrors the FastAPI start-backend.sh but uses gunicorn/uvicorn with
# Django's WSGI/ASGI application instead of uvicorn main:app.

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

# Apply any pending migrations before starting (safe to run on every boot)
echo "Running Django migrations..."
python manage.py migrate --noinput

# Use uvicorn + Django ASGI for SSE streaming support
set -- uvicorn config.asgi:application --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"

if [ "$RELOAD" = "true" ]; then
  set -- "$@" --reload
fi

if [ "$DEBUGPY_ENABLED" = "true" ]; then
  echo "Starting backend with debugpy on ${DEBUGPY_HOST}:${DEBUGPY_PORT}"

  if [ "$DEBUGPY_WAIT" = "true" ]; then
    if [ "$DEBUGPY_SUBPROCESS" = "false" ]; then
      exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --configure-subProcess false --wait-for-client -m "$@"
    fi
    exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --wait-for-client -m "$@"
  fi

  if [ "$DEBUGPY_SUBPROCESS" = "false" ]; then
    exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" --configure-subProcess false -m "$@"
  fi

  exec python -Xfrozen_modules=off -m debugpy --listen "${DEBUGPY_HOST}:${DEBUGPY_PORT}" -m "$@"
fi

exec "$@"
