#!/bin/bash
set -e

# Redis startup script with dynamic password configuration

echo "Starting Redis Stack server..."

# Base configuration file
CONFIG_FILE="/etc/redis/redis.conf"
RUNTIME_CONFIG="/tmp/redis-runtime.conf"

# Copy base configuration
cp "$CONFIG_FILE" "$RUNTIME_CONFIG"

# Add password configuration if REDIS_PASSWORD is set
if [ -n "$REDIS_PASSWORD" ]; then
    echo "Configuring Redis with authentication..."
    echo "requirepass $REDIS_PASSWORD" >> "$RUNTIME_CONFIG"
else
    echo "Starting Redis without authentication..."
fi

# Start Redis Stack server with runtime configuration
exec redis-stack-server "$RUNTIME_CONFIG"
