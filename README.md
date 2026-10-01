# 🐳 RapidPro Docker — surveyor-modern

Docker compose for a **Surveyor-capable RapidPro stack**, aligned to the
[`UbuhingaVizion/rapidpro`](https://github.com/UbuhingaVizion/rapidpro) `modern` branch (RapidPro
v9.0.0, Django 5.2), with the Go service versions chosen to match its schema. It targets the offline
[RapidPro Surveyor](https://github.com/rapidpro/surveyor) Android client (including the upgraded fork).

> ℹ️ Surveyor support is retained by the **AGPL** `rapidpro/mailroom`, which still serves
> `POST /mr/surveyor/submit`. The BSL `nyaruka/mailroom` dropped that endpoint in `v9.1.10`, and
> `nyaruka/courier`/`rp-indexer`/`rp-archiver` flipped to the BSL after the tags pinned here.

## Version locks

| Service | Version | Why |
|---|---|---|
| RapidPro (webapp + celery) | fork `UbuhingaVizion/rapidpro` @ `modern` | RapidPro v9.0.0, Django 5.2, Python 3.12, uv-native, plain Django templates; Surveyor media/API kept |
| Mailroom | sibling `../mailroom` (AGPL `UbuhingaVizion` fork of `rapidpro/mailroom`) | surveyor-capable; retains `POST /mr/surveyor/submit` (BSL `nyaruka/mailroom` removed it in `v9.1.10`) |
| Courier | `v26.3.34` (AGPL) | last AGPL Courier release (`v26.3.35`+ is BSL) |
| rp-indexer | `v26.0.1` (AGPL) | matches the 9.0.0-era schema (ES7) |
| rp-archiver | `v26.0.1` (AGPL) | archives old runs/messages to `temba-archives` (optional for Surveyor) |
| Elasticsearch | `7.17.9` | RapidPro CI version (ES7) |
| PostgreSQL | `postgis/postgis:16-3.5-alpine` | matches RapidPro modern CI |
| Redis | `7.2-alpine` | matches RapidPro modern CI |
| SeaweedFS | `4.47` | S3-compatible object store for media/attachments |
| nginx | latest | routes `/mr/` → mailroom |

## Why this train

- RapidPro `modern` is **uv-native**: PEP 621 `pyproject.toml`, committed `uv.lock`,
  `[tool.uv] package = false`, `uv_build` backend. The image installs with
  `uv sync --frozen --no-dev` for reproducible builds.
- Surveyor server support lives in **Mailroom**, not the web app. The AGPL **`rapidpro/mailroom`**
  keeps `/mr/surveyor/submit`; the BSL `nyaruka/mailroom` removed it in `v9.1.10`. We build from the
  sibling `../mailroom` checkout (AGPL `UbuhingaVizion` fork), so the endpoint survives the v9
  schema/Django 5.2 move. Expect it on the surveyor-capable `rapidpro/mailroom` `main` line
  (currently `f5a17468`, the v9.0.0-era code).
- Courier/rp-indexer/rp-archiver are pinned to the newest **AGPL** releases of the 9.0.0 era
  (Courier `v26.3.34`, rp-indexer/rp-archiver `v26.0.1`); the later tags on each are BSL.

Includes: RapidPro webapp + celery, Mailroom, Courier, rp-indexer, rp-archiver, nginx, PostgreSQL
(PostGIS), Redis, SeaweedFS (S3-compatible object store). These containers are for development/test
use; production hardening is handled in later stages.

## Usage

```bash
cp .env.example .env   # then edit .env (see Configuration below)
docker compose up -d --build
```

The build uses two sibling checkouts (compose additional build contexts): `../rapidpro`
(`UbuhingaVizion/rapidpro` @ `modern`) as RapidPro's source, and `../mailroom`
(`UbuhingaVizion/mailroom`, the AGPL surveyor-capable fork) as Mailroom's source. Both must sit next
to this repo.

The webapp is then at [http://localhost](http://localhost); create a test workspace at
[http://localhost/org/signup](http://localhost/org/signup). For Surveyor to see an org, its flows
must be **type = survey** and the user must hold the **Surveyor** role.

### Configuration

All configurable values live in `.env` (copy from `.env.example`; `.env` is gitignored). Compose
resolves variables with this precedence: **host environment → `.env` → defaults in
`docker-compose.yml`**. To drive values from the host (e.g. `/etc/default/environment`):

```bash
COMPOSE_ENV_FILES=.env,/etc/default/environment docker compose up -d --build
```

or export them in your shell / systemd unit before running compose. Only nginx publishes on
`0.0.0.0` by default; the debug ports (rapidpro/mailroom/courier/elastic) bind to `127.0.0.1`
unless you set `*_BIND=0.0.0.0`.

## Surveyor acceptance gate

After the stack is healthy, run the gate to confirm Surveyor compatibility:

```bash
export RAPIDPRO_EMAIL=<surveyor-role user>
export RAPIDPRO_PASSWORD=<password>
export BASE_URL=http://localhost
./scripts/surveyor_gate.sh
```

It checks: `role=S` authentication, the surveyor v2 endpoints, presence of survey flows with a
supported `spec_version` (11.x/13.x), and that `/mr/surveyor/submit` is **not** 404.

CI (`.github/workflows/gate.yml`) validates the version locks and script syntax on push; the full
stack smoke test is run manually on a docker-capable host (see the script comment).

## Build tooling

- **RapidPro image** builds from the sibling `../rapidpro` checkout (UbuhingaVizion/rapidpro
  `modern`) via the `rapidprosrc` additional build context, so it always uses the local source
  (including uncommitted changes). This repo overlays `rapidpro/docker_settings.py` (copied
  to `temba/settings.py`) and `rapidpro/entrypoint.sh`. It is a **multi-stage build**: the builder
  carries the `-dev` headers/compilers and Node 20, runs `uv sync --frozen --no-dev` and
  `yarn install --frozen-lockfile --production` (RapidPro ships a yarn.lock); the runtime stage keeps
  only the shared libraries actually needed, the built venv, `node_modules` and the source. `node`
  plus a modern `lessc` are kept at runtime because django-compressor runs `lessc` while rendering
  `{% compress %}` tags. The container starts as root only to fix the shared `sitestatic` volume,
  then drops to the unprivileged **`temba` (uid 1000)** user via `gosu`.
- **Go services** build in `mailroom/`, `courier/`, `indexer/`, `archiver/`. Mailroom is compiled
  from the sibling `../mailroom` checkout (AGPL surveyor-capable fork) with `golang:1.26`
  (`CGO_ENABLED=0`, so static) and runs on **Alpine**. Courier/rp-indexer/rp-archiver use nyaruka's
  pinned prebuilt AGPL release binaries, which are glibc-dynamic, so they run on
  **`gcr.io/distroless/base-debian12`** (with a static busybox for the courier healthcheck). All four
  run as non-root (`app`/`nonroot`).
- **Static files** (`/sitestatic/`) are produced by `collectstatic` into the shared `sitestatic`
  volume and served by **nginx** (not the object store, not whitenoise). nginx uses the
  `nginxinc/nginx-unprivileged` image (uid 101, listens on 8080 → host 80).
- All base and service images are pinned by digest. Bump them deliberately (or with a bot such as
  Renovate); the compose file carries the service digests, the Dockerfiles the build digests.
- **User media** is stored in **SeaweedFS** (S3-compatible; all-in-one `weed server -s3`, image
  `chrislusf/seaweedfs:4.47`, cosign-signed) in the `temba-attachments` bucket. The `seaweedfs-init`
  one-shot creates `temba-archives`/`temba-attachments`/`temba-logs`/`temba-sessions` and applies a
  public-read bucket policy to `temba-attachments` (Surveyor downloads media by URL). The S3 port
  (8333) is internal only; nginx proxies `/media/` to that bucket so media URLs are served from the
  same public origin. `temba-archives` is used only by rp-archiver.
- **Background jobs** run as two containers: `celery` (worker, `celery -A temba worker`) and
  `celerybeat` (scheduler, `celery -A temba beat`), split so beat runs exactly once even if you scale
  workers. `docker_settings.py` sets `CELERY_TASK_ALWAYS_EAGER = False`, so tasks queue to Redis.
- **Redis DB must match**: RapidPro queues mailroom batch tasks (contact imports, flow starts,
  broadcasts, campaign events) on its Django **default cache** Redis DB, and mailroom/courier read
  their queues from Redis DB **15**. All four use DB 15 here (`REDIS_URL=redis://redis:6379/15`).
  If you change it, change `MAILROOM_REDIS`/`COURIER_REDIS` too or those jobs silently never run.
- Keep published survey flows at `spec_version` ≤ 13.x so the phone's embedded engine can run them.
- The Android app expects HTTPS in the field; HTTP above is for local testing.

## Deploying on a public domain

Set these in `.env` (or the host environment, e.g. `/etc/default/environment`) before
`docker compose up -d --build`:

| Variable | Example | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | `openssl rand -hex 32` | Django signing key (replace the default) |
| `DJANGO_ALLOWED_HOSTS` | `app.ubuviz.com` | Django host allow-list |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://app.ubuviz.com` | CSRF origins (drop the ngrok entry) |
| `STORAGE_URL` | `https://app.ubuviz.com/media` | base URL returned for Surveyor media |
| `MAILROOM_DOMAIN` / `MAILROOM_ATTACHMENT_DOMAIN` | `app.ubuviz.com` | mailroom-generated URLs |
| `COURIER_DOMAIN` | `app.ubuviz.com` | courier URLs (courier v26 dropped `COURIER_BASE_URL`) |
| `POSTGRES_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `MAILROOM_AUTH_TOKEN` | strong random values | credentials |
| `NGINX_BIND` | `127.0.0.1` | bind nginx to loopback when a host TLS proxy fronts it |

- **Exposure**: nginx binds `127.0.0.1` by default (set `NGINX_BIND=0.0.0.0` only if compose
  nginx is the direct public edge). App debug ports bind loopback; the data stores
  (postgres/redis/elastic/seaweedfs) publish nothing and live on the isolated `rapidpro-data`
  network.
- **Statics**: nginx serves `/sitestatic/` from the `sitestatic` volume — no extra config needed.
- **Media**: nginx serves `/media/` by proxying to SeaweedFS's `temba-attachments` bucket (public-read
  via bucket policy), so keep `STORAGE_URL` pointed at `https://<domain>/media`. The SeaweedFS S3
  port (8333) is intentionally not published; keep it internal.
- **TLS**: terminate HTTPS in front of the compose nginx (a host nginx + certbot, or an external load
  balancer). The host proxy must set `client_max_body_size 100m`, forward `X-Forwarded-Proto $scheme`,
  and add HSTS. The field Surveyor app requires HTTPS.
- If you prefer to serve media directly from SeaweedFS instead of the nginx proxy, set `STORAGE_URL`
  to its public URL (e.g. `https://s3.example.org/temba-attachments`) and expose 8333 with TLS.

## Security model

- **Network isolation**: `rapidpro-data` is an `internal: true` network (no egress, no host
  reachability) holding postgres/redis/elastic/seaweedfs/indexer/archiver. App services are
  dual-homed on `rapidpro-data` + `rapidpro-app` (egress). Elasticsearch is intentionally
  **unauthenticated** (no ES credentials are configured for rp-indexer/mailroom here); it is protected
  by isolation plus the lack of any published port.
- **`/mr/` lockdown**: nginx only proxies `POST /mr/surveyor/submit`; every other `/mr/*` path returns
  `403`. RapidPro reaches the internal mailroom endpoints over the compose network
  (`MAILROOM_URL=http://mailroom:8090`), not through nginx. Open IVR/ticket callbacks explicitly (see
  the commented block in `nginx/default.conf`) only if those channels are used.
- **Component auth**: `MAILROOM_AUTH_TOKEN` (set in `.env`) is required by mailroom's internal routes
  and sent by RapidPro/celery (`Authorization: Token <token>`). Empty disables it.
- **Headers**: nginx sets `X-Content-Type-Options`, `X-Frame-Options` (`SAMEORIGIN`),
  `Referrer-Policy`, and `Permissions-Policy`; Django's duplicates are disabled and Django's
  clickjacking middleware is removed so nginx is the single source. HSTS belongs at the TLS edge.
- **Django**: `SECURE_SSL_REDIRECT`, secure/samesite cookies, and the full password-validator set are
  enabled in `rapidpro/docker_settings.py`.
- **Rate limiting**: nginx rate-limits `/api/v2/authenticate`, `/accounts/login/`, `/org/signup/`,
  `/mr/surveyor/submit`, and `/c/`. Real client IPs are recovered from `X-Forwarded-For` (trusted
  from the app/data subnets).
