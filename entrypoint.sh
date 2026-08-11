#!/bin/sh
set -e

if [ -f /app/bot.py ]; then
  exec python /app/bot.py
else
  echo "bot.py not found in /app" >&2
  exit 1
fi
