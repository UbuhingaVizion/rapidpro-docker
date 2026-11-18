# 🐳 RapidPro Docker — surveyor-modern

Docker compose for a **Surveyor-capable RapidPro stack**, aligned to the
[`UbuhingaVizion/rapidpro`](https://github.com/UbuhingaVizion/rapidpro) `modern` branch (RapidPro
v9.0.0, Django 5.2), with the Go service versions chosen to match its schema. It targets the offline
[RapidPro Surveyor](https://github.com/rapidpro/surveyor) Android client (including the upgraded fork).

> ℹ️ Surveyor support is retained by the **AGPL** `rapidpro/mailroom`, which still serves
> `POST /mr/surveyor/submit`. The BSL `nyaruka/mailroom` dropped that endpoint in `v9.1.10`, and
> `nyaruka/courier`/`rp-indexer`/`rp-archiver` flipped to the BSL after the tags pinned here.

## Version locks

`stack.lock` is the machine-readable pin for the whole stack; `.github/workflows/gate.yml` fails
if the compose build args drift from it.

| Service | Version | Why |
|---|---|---|
| RapidPro (webapp + celery) | fork `UbuhingaVizion/rapidpro` @ `v9.0.0-ubuviz.7` | RapidPro v9.0.0, Django 5.2, Python 3.12, uv-native, plain Django templates; Surveyor media/API kept. `.6` = highcharts 11.4.9 (CVE-2026-118250/118251), dead `rawgit.com` plugin removed, pyotp 2.10 / setuptools 84. `.7` = Sentry error reporting and the 32-character OTP secret column |
| Mailroom | fork `UbuhingaVizion/mailroom` @ `v9.0.0-ubuviz.1` | surveyor-capable; retains `POST /mr/surveyor/submit` (BSL `nyaruka/mailroom` removed it in `v9.1.10`) |
| Courier | fork `UbuhingaVizion/courier` @ `v9.1.19-ubuviz.1` (AGPL) | v9.1.19 is the newest Courier speaking the mailroom fork's protocol (task carries `org_id`, per-event channel types); `.1` adds the TikTok Business Messaging handler |
| rp-indexer | `v26.0.1` (AGPL) | matches the 9.0.0-era schema (ES7) |
| rp-archiver | `v26.0.1` (AGPL) | archives old runs/messages to `temba-archives` (optional for Surveyor; **parked** behind the `archiving` profile — see below) |
| Elasticsearch | `7.17.28` | RapidPro CI version (ES7) |
| PostgreSQL | `postgis/postgis:16-3.5-alpine` | matches RapidPro modern CI |
| Redis | `7.2-alpine` | matches RapidPro modern CI |
| SeaweedFS | `4.52` | S3-compatible object store for media/attachments |
| nginx | `nginxinc/nginx-unprivileged:1.30-alpine` (digest-pinned) | routes `/mr/` → mailroom (1.30 = current stable branch) |

## Why this train

- RapidPro `modern` is **uv-native**: PEP 621 `pyproject.toml`, committed `uv.lock`,
  `[tool.uv] package = false`, `uv_build` backend. The image installs with
  `uv sync --frozen --no-dev` for reproducible builds.
- Surveyor server support lives in **Mailroom**, not the web app. The AGPL **`rapidpro/mailroom`**
  keeps `/mr/surveyor/submit`; the BSL `nyaruka/mailroom` removed it in `v9.1.10`. We build from the
  AGPL `UbuhingaVizion/mailroom` fork (tag `v9.0.0-ubuviz.1`), so the endpoint survives the v9
  schema/Django 5.2 move.
- Courier is pinned to the **mailroom fork's protocol**, not the newest release: `v9.1.19` is the
  last Courier whose mailroom task carries `org_id` and uses the per-event channel task types.
  `v9.1.20` changed the task payload, `v9.1.21` collapsed channel events into one type, and
  `v9.3.18` renamed the queue (`handler` → `tasks:handler`) — none of which the fork understands.
  rp-indexer/rp-archiver are `v26.0.1`.

Includes: RapidPro webapp + celery, Mailroom, Courier, rp-indexer, nginx, PostgreSQL
(PostGIS), Redis, SeaweedFS (S3-compatible object store). These containers are for development/test
use; production hardening is handled in later stages.

## Usage

```bash
cp .env.example .env   # then edit .env (see Configuration below)
docker compose up -d --build
```

RapidPro and Mailroom sources are **fetched at pinned fork tags at build time** (compose build args
`RAPIDPRO_REF` / `MAILROOM_REF`), so no sibling checkouts are required — a fresh clone builds
standalone (it does need network access to GitHub).

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

## Security scanning

Container CVEs are tracked with **Trivy** (`.github/workflows/security.yml`, weekly on Mondays plus
every push/PR):

```bash
# everything the stack runs (pinned images) + the locally built app images, with SBOMs
./scripts/security_scan.sh --include-built --sbom
# -> .security/summary.txt, per-image SARIF/JSON, combined.sarif, *.cdx.json
```

The script reads the image list straight from `docker-compose.yml`, so a pin bump is scanned without
touching the script. Honours `TRIVY=/path/to/trivy` and `OUT_DIR=...`.

**Gate policy**

| Finding | Behaviour |
|---|---|
| CRITICAL **with a published fix** | fails the build |
| CRITICAL with no fix available | reported only (nothing to move) |
| HIGH / MEDIUM / LOW | reported to code scanning + job summary, does not fail |
| accepted | must be listed in `.trivyignore.yaml` with a `statement` and an `expired_at` |

Only CRITICAL gates because almost everything above it is owned by a pin this repo cannot move
(fork lockfiles, EOL Elasticsearch, Debian LTS). The weekly run plus SARIF keeps the HIGH tail
visible instead of turning the build permanently red. Exceptions rot on purpose: `expired_at` makes
Trivy re-enable them, which forces a fresh look.

The summary table therefore splits the two kinds of finding: `CRIT/HIGH/MED/LOW` are **fixable**
(moving a pin can clear them — that is the actionable set), and `UNFIXED` is unfixed HIGH+CRITICAL
(upstream has published no patch; reported, never gates). Reading the table as "we have 400 HIGHs"
is misleading — as of Nov 2026 the RapidPro image is ~400 unfixed-vs-6 fixable.

**Known residual risk** (documented in `.trivyignore.yaml` and below):

- **Elasticsearch 7.17.28** is EOL and the last 7.x; RapidPro 9.0 needs ES7. Mitigation is
  topology, not patching: unauthenticated but on the internal `rapidpro-data` network with no
  published port.
- **Debian packages in the RapidPro image** — the dominant residual. The runtime moved to
  **Debian 13 (trixie)**, which cut the unfixed tail from 402 to **333** HIGH/CRITICAL and the
  unfixed CRITICALs from 8 to 5 (removed: `libpq5` ×34, `libheif` ×16, mbedtls/aom/glib/sqlite, and
  the `apt` finding). What remains is concentrated: **ffmpeg 7.1.5 family, 153** (17 CVEs × 9
  packages) and **krb5, 42**, plus `libmariadb3`/`mariadb-common` (4 CRITICAL, a hard dependency of
  `libgdal36`'s MySQL driver) and `libxml2`. Debian stable does **not** ship fixes for ffmpeg
  promptly, so this tail survives any Debian base — the distro move was still worth it (trixie is
  supported to 2030 vs bookworm's 2028 LTS end, and it brings ffmpeg 7 / GDAL 3.10). ffmpeg cannot
  be dropped: `temba/msgs/media.py` runs it for audio/video conversion on uploaded attachments,
  which is the one reachable path. Verified after the move with an ffmpeg 7.1.5 encode plus
  GeoDjango/GEOS/PROJ spatial queries against PostGIS.
- **Alpine packages in nginx/PostGIS** (`krb5`, `musl`, `libxslt`, `libexpat`) have fixes in the
  Alpine repos but upstream images have not been rebuilt (the digests do not move), so no pull
  helps; `nginx-unprivileged:1.31-alpine` and `:stable-alpine` are identical in this regard.
  `postgis:16-3.7-alpine` would cut 72 → 44 HIGH and needs `ALTER EXTENSION postgis UPDATE`.
- **Courier `v9.1.19-ubuviz.1` / rp-indexer `v26.0.1`** binaries embed old Go toolchains (1.22.x / 1.25.0).
  The protocol/schema locks documented above prevent moving the upstream tags; the courier fork is
  rebuilt from source on the v9.1.19 line so it can carry the TikTok handler.
- **sqlparse 0.5.5** is the one remaining fork-side Python fix and needs the Django 6/smartmin 6.2
  move. **highcharts** was cleared in fork tag `v9.0.0-ubuviz.6` (9.3.0 → 11.4.9, both
  CVE-2026-118250/118251), which also removed a `rawgit.com` plugin script from the dashboard that
  had been loading from a domain dead since 2019. **image-size 0.9.7** remains and is build-only:
  it is a dependency of the prebuilt `@nyaruka/temba-components` package and is never executed
  (the runtime `lessc` comes from `/opt/less`, not `node_modules`).

## Build tooling

- **RapidPro image** builds from the pinned fork tag `UbuhingaVizion/rapidpro@v9.0.0-ubuviz.7`
  (branch `modern`), fetched with `git clone --branch` in the builder (compose build args
  `RAPIDPRO_REPO`/`RAPIDPRO_REF`). Both stages run on **Debian 13 (trixie)** — bookworm is LTS-only
  and had ~400 unpatched findings, and Debian 13 renamed packages after the time_t transition
  (`libgdal32`→`libgdal36`, `libgeos-c1v5`→`libgeos-c1t64`, `libssl3`→`libssl3t64`,
  `libmagic1`→`libmagic1t64`), so a future distro bump has to re-check those names. This repo
  overlays `rapidpro/docker_settings.py` (copied
  to `temba/settings.py`) and `rapidpro/entrypoint.sh`. It is a **multi-stage build**: the builder
  carries the `-dev` headers/compilers and Node 22, runs `uv sync --frozen --no-dev` and
  `yarn install --frozen-lockfile --production` (RapidPro ships a yarn.lock); the runtime stage keeps
  only the shared libraries actually needed, the built venv, `node_modules` and the source. `node`
  plus a modern `lessc` are kept at runtime because django-compressor runs `lessc` while rendering
  `{% compress %}` tags. The container starts as root only to fix the shared `sitestatic` volume,
  then drops to the unprivileged **`temba` (uid 1000)** user via `gosu`.
- **Go services** build in `mailroom/`, `courier/`, `indexer/`, `archiver/`. Mailroom is compiled
  from the pinned fork tag `UbuhingaVizion/mailroom@v9.0.0-ubuviz.1` (AGPL surveyor-capable fork)
  with `golang:1.26` (`CGO_ENABLED=0`, so static) and runs on **Alpine 3.23** (3.20 went EOL in April 2026).
  Courier/rp-indexer/rp-archiver use pinned prebuilt AGPL release binaries (courier from the
  `UbuhingaVizion` fork), which are glibc-dynamic, so they run on **`gcr.io/distroless/base-debian12`** (with a static busybox for the
  courier healthcheck). All four run as non-root (`app`/`nonroot`).
- **Static files** (`/sitestatic/`) are produced by `collectstatic` into the shared `sitestatic`
  volume and served by **nginx** (not the object store, not whitenoise). nginx uses the
  `nginxinc/nginx-unprivileged` image (uid 101, listens on 8080 → host 80).
- All base and service images are pinned by digest. Bump them deliberately (or with a bot such as
  Renovate); the compose file carries the service digests, the Dockerfiles the build digests. Every
  bump is re-scanned by `.github/workflows/security.yml` (see **Security** below).
- The RapidPro image applies **`RAPIDPRO_SECURITY_PINS`** on top of the fork's `uv.lock`
  (`djangorestframework==3.18.3 oauthlib==4.0.1 django==5.2.19 psycopg==3.3.9
  psycopg-binary==3.3.9 certifi==2026.10.23`). These are exact versions, applied with
  `uv pip install` + validated by `uv pip check`, so the build stays reproducible. Drop an entry
  once the fork's lockfile ships it. `sqlparse` *cannot* be patched that way: `smartmin 6.1.0`
  declares `sqlparse<0.6.0`, and the smartmin release that widens it (6.2.x) drops Django 5.2, so
  that fix belongs to the fork's Django 6 upgrade; `setuptools 84` is likewise excluded by the
  fork's `setuptools>=83,<84`. **`celery` is deliberately left at 5.6.3**: 5.7.0 pulls kombu 5.7.0,
  whose Redis transport requires `redis-py >= 6.1` while this fork pins `redis<6`, and beat/worker
  die with `kombu.exceptions.VersionMismatch`.
- **User media** is stored in **SeaweedFS** (S3-compatible; all-in-one `weed server -s3`, image
  `chrislusf/seaweedfs:4.52`, cosign-signed) in the `temba-attachments` bucket. The `seaweedfs-init`
  one-shot creates `temba-archives`/`temba-attachments`/`temba-logs`/`temba-sessions` and applies a
  public-read bucket policy to `temba-attachments` (Surveyor downloads media by URL). The S3 port
  (8333) is internal only; nginx proxies `/media/` to that bucket so media URLs are served from the
  same public origin. `temba-archives` is used only by rp-archiver, which is **parked** behind
  `docker compose --profile archiving up -d archiver`: nothing is older than the 90-day retention yet,
  and `v26.0.1` expects the newer `archives_archive` schema (`uuid`/`location`) while RapidPro v9.0.0
  has `url`, so it would log nightly errors without archiving anything. Pin `v10.3.3` before enabling.
- **Background jobs** run as two containers: `celery` (worker, `celery -A temba worker`) and
  `celerybeat` (scheduler, `celery -A temba beat`), split so beat runs exactly once even if you scale
  workers. `docker_settings.py` sets `CELERY_TASK_ALWAYS_EAGER = False`, so tasks queue to Redis.
- **Redis DB must match**: RapidPro queues mailroom batch tasks (contact imports, flow starts,
  broadcasts, campaign events) on its Django **default cache** Redis DB, and mailroom/courier read
  their queues from Redis DB **15**. All four use DB 15 here (`REDIS_URL=redis://redis:6379/15`).
  If you change it, change `MAILROOM_REDIS`/`COURIER_REDIS` too or those jobs silently never run.
- Keep published survey flows at `spec_version` ≤ 13.x so the phone's embedded engine can run them.
- The Android app expects HTTPS in the field; HTTP above is for local testing.

## Starting at boot

Two layers, because they solve different problems:

1. **`restart: unless-stopped`** on every long-running service (asserted in
   `.github/workflows/gate.yml`; `seaweedfs-init` stays `restart: "no"`). This is what brings
   containers back after a daemon restart or crash — Docker does that itself, with no ordering.
2. **A systemd unit** that runs `docker compose up -d --wait` once the daemon is up. Docker's
   restart policies cannot order startup (`depends_on` health conditions are a Compose concept,
   ignored when dockerd resurrects containers), and `rapidpro` runs `migrate` the moment it starts.
   `--wait` also turns "started" into "actually serving".

The unit is **host configuration, not repo content** — it encodes an absolute project path and an
optional secrets file, so it lives in `/etc/systemd/system/` on the host:

```ini
[Unit]
Description=RapidPro compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/rapidpro-docker    # must contain .env
EnvironmentFile=-/etc/default/environment    # optional host-level overrides
ExecStart=/usr/bin/docker compose up -d --wait --wait-timeout 300
ExecStop=/usr/bin/docker compose stop --timeout 30
TimeoutStartSec=600
TimeoutStopSec=120
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rapidpro-stack.service
systemctl status rapidpro-stack.service      # active (exited) is correct: Type=oneshot
```

`ExecStop` deliberately uses `stop`, never `down`, so `systemctl stop` cannot delete containers or
volumes. `--remove-orphans` is deliberately absent so a manually enabled `--profile archiving`
service is not reaped at boot.

Verify without rebooting: `sudo systemctl restart docker` (exercises layer 1, containers come back
on their own) then `sudo systemctl restart rapidpro-stack` (exercises layer 2, ordered + `--wait`).
`curl -s localhost/healthz` returns `ok` — that endpoint is answered by nginx itself and is what
the edge healthcheck polls, so a webapp that is still migrating cannot mark the edge unhealthy.

Things that are *not* covered by this unit:

- the on-host **smsgateway** dedup engine (payment `call_webhook` target) needs its own unit with
  `After=rapidpro-stack.service`, since it connects to the loopback-published Postgres;
- a **host TLS proxy** in front of `127.0.0.1:80` should also carry `After=rapidpro-stack.service`,
  otherwise the first requests after boot 502;
- the **Cloudflare tunnel** is part of the stack (`cloudflared`), so it is covered.

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
| `COURIER_DOMAIN` | `app.ubuviz.com` | courier callback domain |
| `PUBLIC_DOMAIN` | `app.ubuviz.com` | public hostname for outbound links + Django `HOSTNAME`/`BRAND` |
| `RESEND_API_KEY` / `EMAIL_FROM` | `re_…` / `JengaMarket <no-reply@example.com>` | outbound email (Resend SMTP relay) for invitations/notifications and flow "Send Email"; `EMAIL_FROM` must be on a Resend-verified domain |
| `SENTRY_ENVIRONMENT` / `MAILROOM_SENTRY_DSN` / `COURIER_SENTRY_DSN` / `INDEXER_SENTRY_DSN` / `ARCHIVER_SENTRY_DSN` | `production` / `https://…@….ingest.sentry.io/…` | error reporting for the Go services (RapidPro itself has no SDK in the image); empty DSN disables it |
| `POSTGRES_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `MAILROOM_AUTH_TOKEN`, `MAILROOM_COURIER_AUTH_TOKEN`/`COURIER_AUTH_TOKEN` | strong random values | credentials (courier token pair must match) |
| `NGINX_BIND` | `127.0.0.1` | bind nginx to loopback when a host TLS proxy fronts it |

- **Email**: `SEND_EMAILS` is on and RapidPro sends invitations/notifications through the **Resend
  SMTP relay** (`EMAIL_*` overrides in `rapidpro/docker_settings.py`, since `settings_common` hardcodes
  `smtp.gmail.com`). Template emails take their sender from `branding.emails.notifications`, which
  defaults to `support@rapidpro.io` — pinned to `EMAIL_FROM` (or `NOTIFICATIONS_FROM_EMAIL`) so the
  relay accepts it. Flow "Send Email" is sent by **mailroom**, not Django: it uses the org SMTP config
  in the UI, falling back to `MAILROOM_SMTP_SERVER` (built from `RESEND_API_KEY`). Courier sends no
  email, and v9.0.0 has no password-reset email (admins set passwords).

- **Channels**: `docker compose up -d` starts **Courier** by default (no profile needed). The pinned
  `v9.1.19-ubuviz.1` speaks the mailroom fork's protocol, so inbound messages flow with **no schema shims and
  no patches**. For an on-host SMS gateway (External/EX channel at `host.docker.internal:5000`), set
  `COURIER_DISALLOWED_NETWORKS`/`MAILROOM_DISALLOWED_NETWORKS` (see `.env.example`); both default to
  the secure SSRF policy and are the only place it is relaxed.

- **Exposure**: nginx binds `127.0.0.1` by default (set `NGINX_BIND=0.0.0.0` only if compose
  nginx is the direct public edge). App debug ports bind loopback; the data stores
  (postgres/redis/elastic/seaweedfs) publish nothing and live on the isolated `rapidpro-data`
  network.
- **Statics**: nginx serves `/sitestatic/` from the `sitestatic` volume — no extra config needed.
  Asset filenames are **not content-hashed** (plain static storage), so the location uses a short
  `expires 1h`; a long TTL would keep browsers on the previous release's JS/CSS after a redeploy
  (new HTML + old scripts → `ReferenceError`, dead components).
- **Errors**: mailroom/courier/indexer/archiver ship `sentry-go` and are wired from
  `*_SENTRY_DSN` + `SENTRY_ENVIRONMENT` (empty DSN disables). RapidPro/celery have no Sentry SDK
  in the image, so Django 500s are only in the container logs.
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
- **`/mr/` lockdown**: nginx only proxies `POST /mr/surveyor/submit` and `GET /mr/docs/` (static
  goflow editor docs fetched by the flow editor); every other `/mr/*` path returns
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
