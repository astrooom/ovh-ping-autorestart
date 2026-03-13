#!/bin/bash
# Cron wrapper for OVH server monitor
# Uses flock to guarantee only one instance runs at a time

LOCKFILE="/var/run/ovh-monitor.lock"
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/venv/bin/python3"
SCRIPT="$DIR/monitor-ovh-servers.py"
LOGFILE="/var/log/ovh-monitor.log"

# Load OVH API credentials from .env file
set -a
source "$DIR/.env.ovh-monitor"
set +a

# flock -n: non-blocking, exit immediately if lock is held
# flock wraps the python process — lock is released when python exits
flock -n "$LOCKFILE" "$PYTHON" "$SCRIPT" >> "$LOGFILE" 2>&1
