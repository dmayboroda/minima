#!/bin/bash

set -e

HOST=$1
TIMEOUT=$2

if [ -z "$HOST" ] || [ -z "$TIMEOUT" ]; then
  echo "Usage: $0 <host:port/path> <timeout>"
  exit 1
fi

echo "Waiting for $HOST to return HTTP 200..."

for ((i=1;i<=TIMEOUT;i++)); do
  STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$HOST" || echo "000")
  if [ "$STATUS" -eq 200 ]; then
    echo "Service $HOST is ready."
    exit 0
  fi
  echo "Service $HOST not ready, retrying ($i/$TIMEOUT)..."
  sleep 1
done

echo "Timeout reached while waiting for $HOST"
exit 1
