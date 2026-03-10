#!/bin/bash
# Cron wrapper for OVH server monitor
# Ensures only one instance runs at a time via pidfile

PIDFILE="/var/run/ovh-monitor.pid"
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/venv/bin/python3"
SCRIPT="$DIR/monitor-ovh-servers.py"
LOGFILE="/var/log/ovh-monitor.log"

# Load OVH API credentials from .env file
set -a
source "$DIR/.env.ovh-monitor"
set +a

# Check if already running (pidfile + process name check)
if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE")
    if kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$PIDFILE"
fi

# Extra safety: check if any instance is running by process name
if pgrep -f "monitor-ovh-servers.py" > /dev/null 2>&1; then
    exit 0
fi

# Start monitor
echo $$ > "$PIDFILE"
exec "$PYTHON" "$SCRIPT" >> "$LOGFILE" 2>&1
