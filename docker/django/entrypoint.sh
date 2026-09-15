#!/bin/sh
set -e
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  while ! nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do sleep 1; done
fi
exec "$@"
