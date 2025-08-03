#!/bin/bash
set -e

# Create log directories
mkdir -p /var/log/supervisor /var/log/redis /var/log/fastapi

# Ensure Redis user exists and has proper permissions
if ! id redis &>/dev/null; then
    useradd --system --home /var/lib/redis --shell /bin/false redis
fi

# Set proper permissions
chown -R redis:redis /var/lib/redis /var/log/redis /var/lib/redis-stack
chmod 755 /var/lib/redis /var/log/redis /var/lib/redis-stack

# Start supervisor which will manage both Redis and FastAPI
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
