# AGENTS.md

## What this repo is
- Dev/test-only Docker Compose stack for a **Surveyor-capable** RapidPro (fork `UbuhingaVizion/rapidpro-docker`, branch `feature/LocalStack`). No application source here.
- It pins a matched **RapidPro v9.0.0 / AGPL** service train. Surveyor support comes from the AGPL `rapidpro/mailroom` fork (the BSL `nyaruka/mailroom` removed `/mr/surveyor/submit` in v9.1.10); courier is pinned to `v9.1.19` (the newest release whose mailroom task still carries `org_id` and uses the per-event channel types), rp-indexer/rp-archiver to their newest **AGPL** tags. Do not "upgrade" individual services.
- RapidPro source is the fork `UbuhingaVizion/rapidpro` @ **`v9.0.0-ubuviz.1`** (branch `modern`): RapidPro v9.0.0, Django 5.2, Python 3.12, uv, plain Django templates, Surveyor kept. Its `AGENTS.md` is the source of truth for app-side coupling.
- Mailroom source is the fork `UbuhingaVizion/mailroom` @ **`v9.0.0-ubuviz.1`** (branch `master`; AGPL, surveyor-capable). Both are fetched with `git clone --branch` at build time — no sibling checkouts.

## Commands
- Build + start: `cp .env.example .env` then `docker compose up -d --build` (the only real build).
- Config is env-driven: compose resolves **host env → `.env` → defaults in `docker-compose.yml`**. `.env` is gitignored; `.env.example` documents every variable. To add host-level values (e.g. `/etc/default/environment`): `COMPOSE_ENV_FILES=.env,/etc/default/environment docker compose up -d --build`.
- Validate compose: `docker compose config`. Version-lock assertions live in `.github/workflows/gate.yml`.
- Surveyor gate (needs a running stack + a user with the Surveyor role):
  `RAPIDPRO_EMAIL=... RAPIDPRO_PASSWORD=... BASE_URL=http://localhost ./scripts/surveyor_gate.sh`
- Reset state: `docker compose down -v` (volumes: `postgres`, `elastic`, `redis`, `seaweedfs`, `sitestatic`).
- No unit/lint/typecheck suite. `.github/workflows/ci.yml` only does `cp .env.example .env` → `docker compose config -q` → `docker compose build courier indexer archiver` (the full stack build is too heavy for hosted runners); do not invent more.

## Version locks (move as one train)
- RapidPro: fork `UbuhingaVizion/rapidpro` @ **`v9.0.0-ubuviz.1`** (branch `modern`), set via compose build args `RAPIDPRO_REPO`/`RAPIDPRO_REF`.
- Mailroom: fork `UbuhingaVizion/mailroom` @ **`v9.0.0-ubuviz.1`** (branch `master`; AGPL, surveyor-capable), set via compose build args `MAILROOM_REPO`/`MAILROOM_REF`. The Dockerfiles `git clone --branch` these tags at build time.
- Courier `v9.1.19` (AGPL): the newest Courier that speaks the mailroom fork's protocol. `v9.1.20` changed the mailroom task payload, `v9.1.21` collapsed channel events into a single `channel_event` type, and `v9.3.18` renamed the queue (`handler` → `tasks:handler`); none of those are understood by the fork. rp-indexer `v26.0.1` (AGPL), rp-archiver `v26.0.1` (AGPL).
- Elasticsearch `7.17.9`, PostGIS `16-3.5-alpine`, Redis `7.2-alpine`, SeaweedFS `4.47`.
- Pins are duplicated in `docker-compose.yml` build args, `.github/workflows/gate.yml` asserts, and the README table. Change all three together. Bumping a fork pin means creating+pushing a new tag first.
- Base/service images are also **pinned by digest**: service digests in `docker-compose.yml`, build-stage digests in the Dockerfiles. Bump deliberately.
- Go builds: `mailroom` compiles from the pinned fork tag with `golang:1.26` (`CGO_ENABLED=0` → static, runs on `alpine:3.20`); `courier`/`indexer`/`archiver` download prebuilt release binaries, which are glibc-dynamic, so they run on `gcr.io/distroless/base-debian12` (not Alpine).

## Architecture / gotchas
- `rapidpro`, `celery`, `celerybeat` build the *same* image from `./rapidpro/`, which pulls the source from the pinned fork tag via `git clone --branch` (see the Dockerfile / compose args); `command` selects `webapp`/`worker`/`beat` (`rapidpro/entrypoint.sh`). Webapp runs `migrate` + `collectstatic --clear` then gunicorn. `rapidpro/docker_settings.py` is copied in as `temba/settings.py`.
- **Redis DB 15 must match everywhere**: Django, mailroom, courier all use `redis://redis:6379/15`. Change one and mailroom batch jobs silently never run.
- nginx runs as the **unprivileged** image (uid 101) and listens on **8080**; it serves `/sitestatic/` from the `sitestatic` volume, proxies `/media/` → `seaweedfs:8333` `temba-attachments` bucket, routes `/`→rapidpro:8000 and `/c/`→courier:8080, and **only** proxies `POST /mr/surveyor/submit` to mailroom (all other `/mr/*` → 403). It also sets base security headers, rate-limits auth/surveyor/courier paths, and recovers real client IP from `X-Forwarded-For` (`nginx/default.conf`).
- **Network topology:** `rapidpro-data` (`internal: true`, subnet `172.29.0.0/16`) holds postgres/redis/elastic/seaweedfs/indexer/archiver; app services (rapidpro/celery/celerybeat/mailroom/courier) and nginx are dual-homed on `rapidpro-data` + `rapidpro-app` (`172.28.0.0/16`, egress). Data stores publish no host ports.
- **Elasticsearch is intentionally unauthenticated** (`xpack.security.enabled=false`): no ES credentials are configured for rp-indexer/mailroom here. It is protected only by network isolation — do not expose it.
- **`MAILROOM_AUTH_TOKEN`** is required by mailroom's internal routes and sent by RapidPro/celery as `Authorization: Token <token>`; empty disables it. Set it in `.env`. nginx's `/mr/surveyor/submit` uses the Surveyor's user token instead.
- **Courier starts with plain `docker compose up -d`** (not profile-gated) and, at `v9.1.19`, writes `msgs_msg`/Redis tasks the fork mailroom handles directly — **no DB shim and no build-time patches**. `COURIER_AUTH_TOKEN` (Bearer) guards `POST /c/_fetch-attachment` and must equal mailroom's `MAILROOM_COURIER_AUTH_TOKEN`; empty disables it.
- **Local SMS gateway**: courier and mailroom carry `extra_hosts: host.docker.internal:host-gateway`; `COURIER_DISALLOWED_NETWORKS`/`MAILROOM_DISALLOWED_NETWORKS` are opt-in (empty = secure default; set in `.env` to reach an on-host gateway, dropping only `172.16.0.0/12`); `PUBLIC_DOMAIN` sets Django `HOSTNAME`/`BRAND` for outbound links.
- All app containers run **non-root**: rapidpro/celery/celerybeat and mailroom as uid 1000, courier/indexer/archiver as uid 65532, nginx as 101. The RapidPro entrypoint starts as root only to `chown` the shared `sitestatic` volume, then drops via `gosu`.
- **django-compressor needs `lessc` at runtime** even though `COMPRESS_ENABLED=False`: rendering `{% compress %}` tags invokes it. The runtime image therefore keeps `node` plus a modern global `less` (the pinned `package.json` less@2.7.1 is too old). Dropping it makes every page 500.
- **Django HTTPS hardening** (`docker_settings.py`): `SECURE_SSL_REDIRECT`, secure + `SameSite=Strict` cookies, full password validators; HSTS stays at the TLS edge; nginx owns the base headers, so Django's copies are disabled and the clickjacking middleware is removed.
- SeaweedFS is the only S3 store: all-in-one `weed server -s3` (image `chrislusf/seaweedfs:4.47`), port 8333 internal only; buckets are created by the one-shot `seaweedfs-init` service. Creds `root`/`tembatemba`.
- **Exposure:** `nginx` binds `127.0.0.1:80` by default (host TLS proxy / tunnel); set `NGINX_BIND=0.0.0.0` only if compose nginx is the direct edge. rapidpro/mailroom/courier also bind loopback; postgres/redis/elastic/seaweedfs publish nothing. Bucket names and internal service hostnames are topology, not env config.
- **Secrets** (`POSTGRES_PASSWORD`, `S3_ACCESS_KEY`/`S3_SECRET_KEY`, `DJANGO_SECRET_KEY`, `MAILROOM_AUTH_TOKEN`, `MAILROOM_COURIER_AUTH_TOKEN`/`COURIER_AUTH_TOKEN`) come from `.env`/host env; the compose defaults are dev-only.
- Surveyor constraints: published survey flows must stay `spec_version` ≤ 13.x; the Android app needs HTTPS in the field.

## Node
- The app image uses **Node 20** both to build assets (`yarn install --frozen-lockfile --production`; RapidPro ships a classic `yarn.lock`) and at runtime for django-compressor's `lessc` (a modern global `less` is installed to `/opt/less`). Keep Node 20 to match RapidPro CI.
- There is no Node 18 / Puppeteer E2E harness on this branch (the old `test/main.js` and `package.json` are gone); CI installs no Node.
