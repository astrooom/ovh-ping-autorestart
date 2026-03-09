# OVH Ping Autorestart

Monitors OVH dedicated servers via ping and automatically triggers a hard reboot through the OVH API if a server becomes unreachable for 60 seconds. Sends Slack notifications on all state changes.

## How it works

1. Pings each server every 5 seconds
2. After 12 consecutive failures (60s), triggers `POST /dedicated/server/{name}/reboot` via OVH API
3. Waits 5 minutes cooldown after reboot before resuming monitoring
4. Sends Slack notifications when a server goes down, reboot is triggered, and when it comes back online

## Setup

### 1. Create OVH API credentials

Go to the token creation page for your region:

| Region | URL |
|--------|-----|
| US (OVHcloud US) | https://api.us.ovhcloud.com/createToken/ |
| Europe | https://eu.api.ovh.com/createToken/ |
| Canada | https://ca.api.ovh.com/createToken/ |

Fill in the form:
- **Account ID / Password** — your OVH account login
- **Script name** — e.g. `OVH Auto Reboot`
- **Script description** — e.g. `Triggers reboots on unresponsive dedicated servers`
- **Validity** — `Unlimited` (or set an expiry)
- **Rights** — add these two:
  - `GET` `/me` — used to verify credentials on startup
  - `POST` `/dedicated/server/*` — used to trigger reboots

After submitting you'll receive three values:
- **Application Key**
- **Application Secret**
- **Consumer Key**

### 2. Configure credentials

```bash
cp .env.ovh-monitor.example .env.ovh-monitor
```

Edit `.env.ovh-monitor` and fill in your keys:

```
OVH_ENDPOINT=ovh-us
OVH_APP_KEY=your_application_key
OVH_APP_SECRET=your_application_secret
OVH_CONSUMER_KEY=your_consumer_key
```

Set `OVH_ENDPOINT` to match your region: `ovh-us`, `ovh-eu`, `ovh-ca`, `kimsufi-eu`, `kimsufi-ca`, `soyoustart-eu`, or `soyoustart-ca`.

### 3. Install Python dependencies

```bash
python3 -m venv venv
venv/bin/pip install ovh
```

### 4. Configure servers to monitor

Edit the `SERVERS` list in `monitor-ovh-servers.py`:

```python
SERVERS = [
    ("DISPLAY-NAME", "ns123456.ip-1-2-3.us", "1.2.3.4"),
]
```

- **Display name** — used in Slack notifications and logs
- **Service name** — the OVH internal name (find it in your OVH control panel under the server's General Information, or via `GET /dedicated/server`)
- **IP** — the server's primary IP to ping

### 5. Add cron job

The wrapper script (`run-ovh-monitor.sh`) uses a pidfile to ensure only one instance runs. Cron calls it every minute — if the monitor is already running, it exits immediately.

```bash
crontab -e
```

Add:

```
* * * * * /path/to/ovh-ping-autorestart/run-ovh-monitor.sh
```

### 6. Verify

```bash
# Check logs
tail -f /var/log/ovh-monitor.log

# Check if running
cat /var/run/ovh-monitor.pid && ps -p $(cat /var/run/ovh-monitor.pid)

# Stop manually
kill $(cat /var/run/ovh-monitor.pid)
```

## Files

| File | Purpose |
|------|---------|
| `monitor-ovh-servers.py` | Main monitoring script |
| `run-ovh-monitor.sh` | Cron wrapper with pidfile lock |
| `.env.ovh-monitor` | Credentials (gitignored) |
| `.env.ovh-monitor.example` | Example credentials template |
| `logrotate.conf` | Log rotation config (copy to `/etc/logrotate.d/ovh-monitor`) |
| `venv/` | Python virtual environment |

### Log rotation

Copy the included logrotate config to enable daily log rotation (7 days retained):

```bash
sudo cp logrotate.conf /etc/logrotate.d/ovh-monitor
```

## Slack notifications

Notifications are sent to the configured Slack webhook URL set in `.env.ovh-monitor`.

Message types:
- Server unreachable (first failure + updates every 30s)
- Reboot triggered
- Reboot API call failed
- Server back online (with downtime duration)
