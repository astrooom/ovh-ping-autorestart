#!/usr/bin/env python3
"""
OVH Dedicated Server Monitor
Monitors servers via ping and triggers OVH API reboot if unreachable for 60 seconds.
Sends Slack notifications on state changes and reboots.
"""

import subprocess
import threading
import time
import json
import sys
import os
import logging
from datetime import datetime, timedelta

try:
    import ovh
except ImportError:
    print("ERROR: 'ovh' package not installed. Run: pip install ovh")
    sys.exit(1)

# ─── Configuration ───────────────────────────────────────────────────────────

# OVH API credentials
OVH_ENDPOINT = os.environ.get("OVH_ENDPOINT", "ovh-us")
OVH_APP_KEY = os.environ.get("OVH_APP_KEY", "")
OVH_APP_SECRET = os.environ.get("OVH_APP_SECRET", "")
OVH_CONSUMER_KEY = os.environ.get("OVH_CONSUMER_KEY", "")

# Slack webhook
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Servers to monitor: (display_name, service_name, ip)
SERVERS = [
    ("GAME-O-HIL1-1018625-US", "ns1018625.ip-15-204-44.us", "15.204.44.62"),
    ("GAME-O-HIL1-1020759-US", "ns1020759.ip-15-204-44.us", "15.204.44.142"),
]

# Monitoring thresholds
PING_INTERVAL = 5        # seconds between pings
FAIL_THRESHOLD = 60      # seconds of failed pings before reboot
COOLDOWN_AFTER_REBOOT = 300  # seconds to wait after triggering reboot

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ovh-monitor")

# ─── Helpers ─────────────────────────────────────────────────────────────────


def ping(ip):
    """Returns True if host responds to a single ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except Exception:
        return False


def slack_notify(text):
    """Send a notification to Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        payload = json.dumps({"text": text})
        subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "-H", "Content-type: application/json",
                "--data", payload,
                SLACK_WEBHOOK_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception as e:
        log.error(f"Failed to send Slack notification: {e}")


def reboot_server(client, service_name):
    """Trigger a hard reboot via OVH API. Returns True on success."""
    try:
        client.post(f"/dedicated/server/{service_name}/reboot")
        return True
    except Exception as e:
        log.error(f"OVH API reboot failed for {service_name}: {e}")
        return False


# ─── Per-server monitor ─────────────────────────────────────────────────────


def monitor_server(client, display_name, service_name, ip):
    """Monitoring loop for a single server."""
    consecutive_failures = 0
    max_failures = FAIL_THRESHOLD // PING_INTERVAL
    was_down = False

    log.info(f"[{display_name}] Monitoring {ip} (reboot after {FAIL_THRESHOLD}s down)")

    while True:
        if ping(ip):
            if was_down:
                elapsed = consecutive_failures * PING_INTERVAL
                msg = f":white_check_mark: *{display_name}* (`{ip}`) is back online after ~{elapsed}s of downtime"
                log.info(f"[{display_name}] Back online")
                slack_notify(msg)
                was_down = False
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            elapsed = consecutive_failures * PING_INTERVAL
            log.warning(f"[{display_name}] Ping failed ({elapsed}/{FAIL_THRESHOLD}s)")

            if not was_down:
                was_down = True

            if consecutive_failures >= max_failures:
                msg = (
                    f":rotating_light: *{display_name}* (`{ip}`) unreachable for {FAIL_THRESHOLD}s — triggering OVH API reboot"
                )
                log.error(f"[{display_name}] Down for {FAIL_THRESHOLD}s, rebooting via API")
                slack_notify(msg)

                if reboot_server(client, service_name):
                    log.info(f"[{display_name}] Reboot triggered, waiting {COOLDOWN_AFTER_REBOOT}s cooldown")
                    slack_notify(
                        f":arrows_counterclockwise: *{display_name}* reboot command sent. Waiting {COOLDOWN_AFTER_REBOOT // 60}min for server to come back."
                    )
                else:
                    slack_notify(
                        f":x: *{display_name}* — OVH API reboot FAILED. Manual intervention required."
                    )

                consecutive_failures = 0
                time.sleep(COOLDOWN_AFTER_REBOOT)
                continue

        time.sleep(PING_INTERVAL)


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    # Validate credentials
    if not all([OVH_APP_KEY, OVH_APP_SECRET, OVH_CONSUMER_KEY]):
        log.error(
            "OVH API credentials not set. Export OVH_APP_KEY, OVH_APP_SECRET, OVH_CONSUMER_KEY"
        )
        sys.exit(1)

    # Init OVH client
    try:
        client = ovh.Client(
            endpoint=OVH_ENDPOINT,
            application_key=OVH_APP_KEY,
            application_secret=OVH_APP_SECRET,
            consumer_key=OVH_CONSUMER_KEY,
        )
        # Verify credentials with a lightweight call
        me = client.get("/me")
        log.info(f"OVH API authenticated as: {me.get('nichandle', 'unknown')}")
    except Exception as e:
        log.error(f"Failed to initialize OVH API client: {e}")
        sys.exit(1)

    slack_notify(
        f":satellite: OVH server monitor started — watching {len(SERVERS)} server(s)"
    )

    # Launch a monitoring thread per server
    threads = []
    for display_name, service_name, ip in SERVERS:
        t = threading.Thread(
            target=monitor_server,
            args=(client, display_name, service_name, ip),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Shutting down")
        slack_notify(":octagonal_sign: OVH server monitor stopped")


if __name__ == "__main__":
    main()
