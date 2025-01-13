#!/bin/bash

# Download rclone config from URL if provided
if [ ! -z "$RCLONE_CONFIG_URL" ]; then
    echo "Downloading rclone config from $RCLONE_CONFIG_URL..."
    curl -o /config/rclone/rclone.conf "$RCLONE_CONFIG_URL"
    echo "Config file downloaded to /config/rclone/rclone.conf"
else
    echo "No RCLONE_CONFIG_URL provided."
fi

# Create empty config if none exists
if [ ! -f /config/rclone/rclone.conf ]; then
    echo "No rclone config found. Creating empty config file..."
    mkdir -p /config/rclone
    touch /config/rclone/rclone.conf
fi

# Set RCLONE_CONFIG environment variable
export RCLONE_CONFIG="/config/rclone/rclone.conf"

# Start FastAPI server
echo "Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 5572 --reload
