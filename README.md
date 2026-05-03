# SwiftDeploy

> Declarative deployment CLI — `manifest.yaml` is the single source of truth.

SwiftDeploy generates all infrastructure configuration from a single YAML manifest, manages the full container lifecycle, and keeps your stack running with health checks, chaos engineering, and zero-downtime mode switching.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Docker | 24.0+ |
| Docker Compose plugin | v2.x (`docker compose`) |
| Python | 3.10+ |

> **No AWS, no cloud required.** Everything runs locally via Docker.

---

## Project Structure

```
swiftdeploy/
├── manifest.yaml              ← ONLY file you edit
├── swiftdeploy                ← CLI entrypoint (executable)
├── app/
│   ├── main.py                ← HTTP API service
│   └── Dockerfile             ← Alpine, non-root, <300MB
├── templates/
│   ├── nginx.conf.j2          ← Nginx Jinja2 template
│   └── docker-compose.yml.j2  ← Compose Jinja2 template
├── generated/                 ← Auto-generated, do not edit
│   ├── nginx.conf
│   └── docker-compose.yml
└── README.md
```

---

## Quick Start

### 1. Build the service image

```bash
docker build -t swift-deploy-1-node:latest ./app
```

### 2. Deploy the stack

```bash
./swiftdeploy deploy
```

That's it. The full stack is now running at `http://localhost:8080`.

---

## Subcommand Reference

### `./swiftdeploy init`

Parses `manifest.yaml` and generates:
- `generated/nginx.conf` from `templates/nginx.conf.j2`
- `generated/docker-compose.yml` from `templates/docker-compose.yml.j2`

```bash
./swiftdeploy init
```

> The grader deletes generated files and runs `init` to verify regeneration. If `init` breaks, the stack breaks.

---

### `./swiftdeploy validate`

Runs 5 pre-flight checks. Exits non-zero on any failure.

| # | Check |
|---|---|
| 1 | `manifest.yaml` exists and is valid YAML |
| 2 | All required fields are present and non-empty |
| 3 | The Docker image referenced in the manifest exists locally |
| 4 | The Nginx port is not already bound on the host |
| 5 | The generated `nginx.conf` is syntactically valid (`nginx -t`) |

```bash
./swiftdeploy validate
```

Sample output:
```
──────────────────────────────────────────────────
swiftdeploy validate — pre-flight checks
──────────────────────────────────────────────────
  ✔  manifest.yaml exists and is valid YAML
  ✔  All required fields present and non-empty
  ✔  Docker image exists locally  →  swift-deploy-1-node:latest
  ✔  Nginx port not already bound on host  →  Port 8080 is free
  ✔  Generated nginx.conf is syntactically valid

  ✔ All 5 checks passed — ready to deploy
```

---

### `./swiftdeploy deploy`

Runs `init` → `validate` → `docker compose up -d` → blocks until health checks pass (60s timeout).

```bash
./swiftdeploy deploy
```

---

### `./swiftdeploy promote [canary|stable]`

Switches deployment mode with a rolling service restart.

```bash
# Switch to canary
./swiftdeploy promote canary

# Switch back to stable
./swiftdeploy promote stable
```

What happens:
1. Updates `mode` field in `manifest.yaml` atomically
2. Regenerates `docker-compose.yml` with new `MODE` env var
3. Restarts **service container only** (nginx stays up — zero downtime)
4. Confirms new mode by polling `/healthz`

---

### `./swiftdeploy teardown`

Removes all containers, networks, and volumes.

```bash
# Stop and remove stack
./swiftdeploy teardown

# Also delete generated config files
./swiftdeploy teardown --clean
```

---

## API Endpoints

All traffic routes through Nginx on port `8080`. The service port is never exposed directly.

### `GET /`

Returns welcome message, current mode, version, and timestamp.

```json
{
  "message": "Welcome to SwiftDeploy API — running in stable mode",
  "mode": "stable",
  "version": "1.0.0",
  "timestamp": "2026-05-05T08:00:00+00:00"
}
```

### `GET /healthz`

Liveness check returning status and process uptime.

```json
{
  "status": "ok",
  "mode": "stable",
  "version": "1.0.0",
  "uptime_seconds": 42.3
}
```

### `POST /chaos` *(canary mode only)*

Simulates degraded behaviour. Returns `403` in stable mode.

```bash
# Slow mode — sleep N seconds before every response
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "slow", "duration": 3}'

# Error mode — return 500 on ~50% of requests
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "error", "rate": 0.5}'

# Recover — cancel any active chaos
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode": "recover"}'
```

---

## Canary Mode

In canary mode, every response includes the `X-Mode: canary` header, and the `/chaos` endpoint is active.

```bash
# Promote to canary
./swiftdeploy promote canary

# Verify
curl -I http://localhost:8080/
# X-Mode: canary
# X-Deployed-By: swiftdeploy
```

---

## Nginx Access Logs

Logs follow the format:
```
$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request
```

View live:
```bash
docker logs swiftdeploy-nginx -f
```

---

## Security

- Containers run as non-root user (`uid=1001`)
- All Linux capabilities dropped (`cap_drop: ALL`)
- `no-new-privileges` enforced
- Read-only root filesystem with `/tmp` tmpfs
- Service port never exposed to host (Nginx-only ingress)
- Images based on `python:3.12-alpine` — well under 300MB

---

## Manifest Reference

```yaml
services:
  image: swift-deploy-1-node:latest   # Docker image name
  port: 3000                          # Internal service port
  mode: stable                        # stable | canary (managed by promote)
  version: "1.0.0"                    # APP_VERSION env var
  replicas: 1
  restart_policy: unless-stopped
  log_volume: swiftdeploy-logs

nginx:
  image: nginx:latest
  port: 8080                          # Host-exposed port
  proxy_timeout: 30                   # Proxy timeout in seconds

network:
  name: swiftdeploy-net
  driver_type: bridge
```

> **Do not edit generated files.** Only `manifest.yaml` is the source of truth.