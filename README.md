# 🐳 RapidPro Docker — surveyor-modern

Docker compose for a **Surveyor-capable RapidPro stack**, aligned to the
[`UbuhingaVizion/rapidpro`](https://github.com/UbuhingaVizion/rapidpro) `develop` branch, with the
Go service versions chosen to match its `v7.4.2` database schema. It targets the offline
[RapidPro Surveyor](https://github.com/rapidpro/surveyor) Android client (including the upgraded fork).

> ⚠️ This is deliberately **not** the latest RapidPro. Upstream removed Surveyor support in Mailroom
> `v9.1.10`. This stack stays on the matching `7.x` service train that still serves
> `POST /mr/surveyor/submit`.

## Version locks

| Service | Version | Why |
|---|---|---|
| RapidPro (webapp + celery) | fork `UbuhingaVizion/rapidpro` @ `develop` | Django 4.2 LTS, Python 3.12, uv-native; Surveyor media/API kept compatible |
| Mailroom | `v7.5.13` | last Surveyor-capable release matching develop's v7.4.2 schema (`flows_flowsession.connection_id`); serves `POST /mr/surveyor/submit` |
| Courier | `v7.5.13` | matches the mailroom train |
| rp-indexer | `v7.4.0` | matches RapidPro develop CI |
| rp-archiver | `v7.5.0` | archives old runs/messages to `temba-archives` (optional for Surveyor) |
| Elasticsearch | `7.17.9` | RapidPro develop CI version (ES7) |
| PostgreSQL | `postgis/postgis:16-3.5-alpine` | matches RapidPro develop CI |
| Redis | `7.2-alpine` | matches RapidPro develop CI |
| MinIO | latest | S3 emulator for media/attachments |
| nginx | latest | routes `/mr/` → mailroom |

## Why this train

- RapidPro `develop` is **uv-native**: PEP 621 `pyproject.toml`, committed `uv.lock`,
  `[tool.uv] package = false`, `uv_build` backend. The image installs with
  `uv sync --frozen --no-dev` for reproducible builds.
- The `7.x` Mailroom/Courier/rp-indexer releases pair with the RapidPro `7.x` (Django 4.2) schema.
  The critical constraint is the flow-session column: `develop` uses `flows_flowsession.connection_id`,
  and Mailroom switched to `call_id` in `v7.5.14`. Mailroom **`v7.5.13`** is therefore the last release
  that both matches this schema and still registers `/mr/surveyor/submit` (removed upstream in
  `v9.1.10`). Its Surveyor submit handler is identical to `v7.5.36`'s — only the session column name
  differs — so the upgraded Surveyor client talks to it the same way.
- We deliberately do **not** move to Django 5.x yet: that requires migrating the Haml templates off
  `django-hamlpy` and a smartmin 4→5 upgrade — a separate project.

Includes: RapidPro webapp + celery, Mailroom, Courier, rp-indexer, rp-archiver, nginx, PostgreSQL
(PostGIS), Redis, MinIO (S3 emulator). These containers are for development/test use; production
hardening is handled in later stages.

## Usage

```bash
docker compose up -d --build
```

The webapp is then at [http://localhost](http://localhost); create a test workspace at
[http://localhost/org/signup](http://localhost/org/signup). For Surveyor to see an org, its flows
must be **type = survey** and the user must hold the **Surveyor** role.

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

- **RapidPro image** runs Python 3.12 and installs dependencies with **uv** (`uv sync --frozen
  --no-dev`) from the committed `uv.lock`. It also installs **Node 20 + npm** and runs `npm install`
  so the flow-editor and temba-components static assets exist for `collectstatic`.
- **Go services** (Mailroom/Courier/rp-indexer/rp-archiver) have no upstream Dockerfiles or published
  images, so each is compiled from source at its pinned tag with the current Go toolchain
  (`golang:1.26`) in `mailroom/`, `courier/`, `indexer/`, and `archiver/`.
- **Static files** (`/sitestatic/`) are produced by `collectstatic` into the shared `sitestatic`
  volume and served by **nginx** (not MinIO, not whitenoise).
- **User media** is stored in **MinIO** (the S3 replacement) in the `temba-archives` bucket. The
  `minio-init` one-shot service creates `temba-archives`/`temba-attachments`/`temba-logs`/
  `temba-sessions` and makes `temba-archives` publicly readable. nginx proxies `/media/` to that
  bucket so media URLs are served from the same public origin.
- Keep published survey flows at `spec_version` ≤ 13.x so the phone's embedded engine can run them.
- The Android app expects HTTPS in the field; HTTP above is for local testing.

## Deploying on a public domain

Set these before `docker compose up -d --build` (e.g. in a `.env` file):

| Variable | Example | Purpose |
|---|---|---|
| `DJANGO_ALLOWED_HOSTS` | `rapidpro.example.org` | Django host allow-list |
| `DJANGO_SECRET_KEY` | long random string | signing key (replace the default) |
| `STORAGE_URL` | `https://rapidpro.example.org/media` | base URL returned for Surveyor media |
| `MAILROOM_DOMAIN` / `MAILROOM_ATTACHMENT_DOMAIN` | `rapidpro.example.org` | mailroom-generated URLs |
| `COURIER_DOMAIN` / `COURIER_BASE_URL` | `rapidpro.example.org` / `https://rapidpro.example.org` | courier URLs |

- **Statics**: nginx serves `/sitestatic/` from the `sitestatic` volume — no extra config needed.
- **Media**: nginx serves `/media/` by proxying to MinIO's `temba-archives` bucket, so keep
  `STORAGE_URL` pointed at `https://<domain>/media`. Don't expose the MinIO console (9001) publicly.
- **TLS**: terminate HTTPS in front of nginx (an external load balancer, or add a TLS server block /
  certbot sidecar). The field Surveyor app requires HTTPS.
- If you prefer to serve media directly from MinIO instead of the nginx proxy, set `STORAGE_URL` to
  the MinIO public URL (e.g. `https://minio.example.org/temba-archives`) and expose 9000 with TLS.
