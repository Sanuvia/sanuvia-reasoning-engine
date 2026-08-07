# Deployment — Sanuvia Engineering Review Harness

Production deployment of the Phase 0 Engineering Review Harness to
**buyafraction.com** (server `192.168.160.98`).

This is a **deployment/operations** layer only. It runs the existing
stdlib-only application unchanged:

```
Browser ──HTTPS──> Caddy (reverse proxy, TLS) ──HTTP──> systemd service
                                                          (127.0.0.1:8000)
                                                                │
                                                          SQLite on disk
                                                          /var/lib/sanuvia
```

- The application is a **systemd service** running the built-in
  `ThreadingHTTPServer`, bound to `127.0.0.1` only.
- **Caddy** terminates HTTPS for `buyafraction.com` and reverse-proxies to the
  local service. It sets the `X-Forwarded-*` headers automatically.
- Reasoning state and saved Review Datasets persist in **SQLite** under
  `/var/lib/sanuvia`, which survives restarts and updates.
- No Docker. No cloud SDK. No framework. The core has zero runtime dependencies.

The reasoning engine, domain model, and Application API are **untouched**. The
deployment only exposes the existing app; every rendered artifact remains
byte-identical (the hash seed is pinned — see *Determinism* below).

---

## 1. Server requirements

| Item | Requirement |
| --- | --- |
| OS | Ubuntu 22.04 LTS or newer |
| Python | 3.11+ (`python3`, `python3-venv`) — installed by `deploy.sh` |
| Privileges | `sudo`/root for first-time provisioning |
| Reverse proxy | Caddy 2.x (for HTTPS) |
| Disk | ~200 MB for the app + venv; SQLite data grows slowly |
| Network | Inbound 443 (and 80 for ACME) to Caddy; the app itself stays on localhost |
| DNS | `buyafraction.com` resolving to this host (see *Troubleshooting → TLS*) |

Canonical paths (override in `/etc/sanuvia/deploy.conf` if needed):

| Path | Purpose |
| --- | --- |
| `/opt/sanuvia` | Git checkout + virtualenv (`.venv`) |
| `/var/lib/sanuvia` | Persistent SQLite DBs + saved Review Datasets |
| `/etc/sanuvia/sanuvia.env` | Service environment (from `.env.example`) |
| `/var/backups/sanuvia` | Backup archives |
| `/etc/systemd/system/sanuvia.service` | systemd unit |
| `/etc/caddy/Caddyfile` | Reverse-proxy config |

---

## 2. Install Docker

Not applicable — this deployment does **not** use Docker. The app runs directly
under systemd. (A `Dockerfile`/`docker-compose.yml` remain in the repo for local
experimentation but are not part of the production path.)

---

## 3. Clone from GitHub

```bash
sudo mkdir -p /opt
sudo git clone https://github.com/eelitedesire/sanuvia.git /opt/sanuvia
cd /opt/sanuvia
```

---

## 4. Configure `.env`

`deploy.sh` installs `/etc/sanuvia/sanuvia.env` from `.env.example` on first run.
Review it — the defaults are production-ready:

```bash
sudo cp /opt/sanuvia/.env.example /etc/sanuvia/sanuvia.env   # deploy.sh also does this
sudoedit /etc/sanuvia/sanuvia.env
```

Every variable is documented inline in [`.env.example`](../.env.example). Key
ones:

| Variable | Production value | Meaning |
| --- | --- | --- |
| `SANUVIA_HOST` | `127.0.0.1` | Bind localhost only; Caddy fronts it |
| `SANUVIA_PORT` | `8000` | Local port Caddy proxies to |
| `SANUVIA_BACKEND` | `sqlite` | Durable persistence (required) |
| `SANUVIA_DB_PATH` | `/var/lib/sanuvia/sanuvia.db` | SQLite database base path |
| `SANUVIA_TESTCASE_DIR` | `/var/lib/sanuvia/testcases` | Saved Review Datasets |
| `PYTHONHASHSEED` | `0` | Determinism (do not change) |

---

## 5. Provision and start (`docker compose up -d` equivalent)

There is no compose command; provisioning is one script:

```bash
sudo /opt/sanuvia/scripts/deploy.sh
```

This installs prerequisites, creates the `sanuvia` service user, the data
directory, the virtualenv, the env file, and the systemd unit, then
`enable --now`s the service and waits for `/health` to return `ok`.

Then put Caddy in front for HTTPS:

```bash
# Install Caddy (official apt repo) if not already present:
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# Install the site config and reload:
sudo cp /opt/sanuvia/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Verify:

```bash
/opt/sanuvia/scripts/status.sh
curl -s http://127.0.0.1:8000/health       # {"status":"ok","version":"phase0","backend":"sqlite"}
curl -s https://buyafraction.com/health    # same, through Caddy
```

---

## 6. Updating from GitHub

The supported update flow is `git pull` → reinstall → verify → restart, wrapped
in one script that **backs up first** and **gates on the deterministic Exit
Test** (it will not restart onto code that fails the Phase 0 proof):

```bash
sudo /opt/sanuvia/scripts/update.sh
```

Equivalent manual commands (what the script runs):

```bash
cd /opt/sanuvia
sudo -u sanuvia git pull --ff-only origin main
sudo -u sanuvia /opt/sanuvia/.venv/bin/pip install --quiet /opt/sanuvia
sudo -u sanuvia /opt/sanuvia/.venv/bin/python -m sanuvia.exit_test   # must PASS
sudo systemctl restart sanuvia
```

---

## 7. Backup

Consistent, online backups (no downtime; SQLite copied via its backup API):

```bash
sudo /opt/sanuvia/scripts/backup.sh
# -> /var/backups/sanuvia/sanuvia-YYYYmmdd-HHMMSS.tar.gz
```

An archive contains every SQLite database plus all saved Review Datasets and a
`BACKUP_MANIFEST.txt` (host, timestamp, git commit). The script keeps the most
recent `BACKUP_RETENTION` (default 14) archives. Copy them off-host regularly.

---

## 8. Restore

```bash
sudo /opt/sanuvia/scripts/restore.sh latest
# or a specific archive:
sudo /opt/sanuvia/scripts/restore.sh /var/backups/sanuvia/sanuvia-20260807-120000.tar.gz
```

The service is stopped, the current data directory is moved aside
(`…-prerestore-<ts>`, so a bad restore is recoverable), the archive is unpacked,
and the service is restarted and health-checked.

---

## 9. Logs

```bash
/opt/sanuvia/scripts/logs.sh                 # follow live
/opt/sanuvia/scripts/logs.sh -n 200          # last 200 lines
/opt/sanuvia/scripts/logs.sh --since "1 hour ago"
```

Application logs go to **journald** (rotated by systemd-journald;
cap with `SystemMaxUse=` in `/etc/systemd/journald.conf` if desired). Caddy
access logs rotate by size/count under `/var/log/caddy/` (see the `Caddyfile`).

---

## 10. Restart / status

```bash
sudo /opt/sanuvia/scripts/restart.sh    # restart + health check
/opt/sanuvia/scripts/status.sh          # service state, health, commit, data, backups
```

---

## 11. Troubleshooting

**Service won't start / unhealthy**
```bash
sudo systemctl status sanuvia --no-pager
/opt/sanuvia/scripts/logs.sh -n 100
```
Common causes: `/var/lib/sanuvia` not writable by `sanuvia` (fix ownership), or a
bad value in `/etc/sanuvia/sanuvia.env`.

**`/health` works locally but not via the domain** — Caddy isn't reaching the
app or TLS isn't issued:
```bash
sudo systemctl status caddy --no-pager
sudo journalctl -u caddy -n 100 --no-pager
curl -s http://127.0.0.1:8000/health     # app up?
```

**TLS / certificate issues (private IP `192.168.160.98`).** Caddy's automatic
HTTPS needs a public ACME challenge (public DNS + reachable 80/443). Options,
documented at the bottom of [`deploy/Caddyfile`](../deploy/Caddyfile):
1. Public DNS for `buyafraction.com` + port-forward 80/443 → this host (config
   works as-is; real trusted cert).
2. Internal only: add `tls internal` to the site block — Caddy issues a cert from
   its own local CA; reviewers trust Caddy's root once
   (`caddy trust` on the client, or import `/var/lib/caddy/.local/share/caddy/pki/`).
3. DNS-01 challenge with a Caddy DNS-provider build (public cert, no open 80/443).

**Reasoning looks wrong after an update** — the Exit Test gate should have caught
it. Re-run it and, if it fails, roll back:
```bash
sudo -u sanuvia /opt/sanuvia/.venv/bin/python -m sanuvia.exit_test
sudo /opt/sanuvia/scripts/restore.sh latest      # if needed
```

**Port already in use** — change `SANUVIA_PORT` in `/etc/sanuvia/sanuvia.env`,
update the `reverse_proxy` target in the `Caddyfile`, then restart both.

---

## Determinism guarantee

The deployment preserves Phase 0 determinism end-to-end:

- The reasoning engine, domain, and Application API are unchanged.
- `PYTHONHASHSEED=0` is pinned in both the systemd unit and the env file, so any
  hash-dependent iteration is stable process-to-process.
- The only code touched for deployment is the **HTTP/persistence adapter layer**:
  a `/health` endpoint, `Cache-Control` headers, and `check_same_thread=False` on
  the SQLite connection (the threading server serialises every request under one
  lock, so this is safe and changes no stored data).
- Running the same Review Dataset twice yields byte-identical trace, graph,
  report, and review-package artifacts.

## Reverse-proxy readiness

The application works behind Nginx or Caddy with no code changes:
- It never constructs absolute URLs and never redirects, so it is agnostic to the
  external scheme/host.
- It honours proxying transparently; Caddy forwards `X-Forwarded-Proto`,
  `X-Forwarded-Host`, and `X-Forwarded-For`, and preserves the original `Host`.
- HTTPS is terminated at the proxy; the app speaks plain HTTP on localhost.
- `/api/*` and `/health` are marked `no-store`; static assets are cacheable at
  the edge (see the `Caddyfile`). An Nginx equivalent: `proxy_pass
  http://127.0.0.1:8000;` with `proxy_set_header X-Forwarded-Proto $scheme;` and
  `add_header Cache-Control no-store;` on `location /api/`.
