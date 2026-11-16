#!/bin/sh
set -e

# Ensure data directory and fonts directory exist
mkdir -p /app/data/fonts

# Copy default bundled fonts if they don't already exist in the mounted volume
if [ -d "/app/bundled_fonts" ]; then
    cp -n /app/bundled_fonts/* /app/data/fonts/ 2>/dev/null || true
fi

# Execute CMD passed to container
exec "$@"

