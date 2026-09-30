# AGENTS.md

## What this repo is
- Dev/test-only Docker Compose stack for a **Surveyor-capable** RapidPro (fork `UbuhingaVizion/rapidpro-docker`, branch `feature/LocalStack`). No application source here.
- It deliberately pins a **7.x** service train, not latest: upstream Mailroom removed `/mr/surveyor/submit` in v9.1.10 and renamed `flows_flowsession.connection_id`→`call_id` in v7.5.14. Do not "upgrade" individual services.
- RapidPro source is the sibling checkout `../rapidpro` (GitHub `UbuhingaVizion/rapidpro` @ `develop`): Django 4.2, Python 3.12, uv, HAML templates, Surveyor kept. Its `AGENTS.md` is the source of truth for app-side coupling.

## Commands
- Build + start: `docker compose up -d --build` (the only real build).
- Validate compose: `docker compose config`. Version-lock assertions live in `.github/workflows/gate.yml`.
- Surveyor gate (needs a running stack + a user with the Surveyor role):
  `RAPIDPRO_EMAIL=... RAPIDPRO_PASSWORD=... BASE_URL=http://localhost ./scripts/surveyor_gate.sh`
- Reset state: `docker compose down -v` (volumes: `postgres`, `elastic`, `redis`, `seaweedfs`, `sitestatic`).
- No unit/lint/typecheck suite. `.github/workflows/ci.yml` only runs `docker compose up -d`; do not invent more.

## Version locks (move as one train)
- RapidPro: the **sibling checkout `../rapidpro`** (GitHub `UbuhingaVizion/rapidpro` @ `develop`), wired in as the compose `rapidprosrc` additional build context — build with the checkout present at `../rapidpro`.
- Mailroom `v7.5.13`, Courier `v7.5.13`, rp-indexer `v7.4.0`, rp-archiver `v7.5.0`.
- Elasticsearch `7.17.9`, PostGIS `16-3.5-alpine`, Redis `7.2-alpine`, SeaweedFS `4.47`.
- Pins are duplicated in `docker-compose.yml` build args, `.github/workflows/gate.yml` asserts, and the README table. Change all three together.
- Go builds: `mailroom` compiles from source (`golang:1.26`, `GOPROXY=https://goproxy.io,direct` + retries); `courier`/`indexer`/`archiver` download prebuilt release binaries (source builds were unreliable).

## Architecture / gotchas
- `rapidpro`, `celery`, `celerybeat` build the *same* image from `./rapidpro/`, which pulls the source from the sibling `../rapidpro` checkout via the `rapidprosrc` additional build context; `command` selects `webapp`/`worker`/`beat` (`rapidpro/entrypoint.sh`). Webapp runs `migrate` + `collectstatic --clear` then gunicorn. `rapidpro/docker_settings.py` is copied in as `temba/settings.py`.
- **Redis DB 15 must match everywhere**: Django, mailroom, courier all use `redis://redis:6379/15`. Change one and mailroom batch jobs silently never run.
- nginx (port 80) serves `/sitestatic/` from the `sitestatic` volume, proxies `/media/` → `seaweedfs:8333` `temba-attachments` bucket, routes `/`→rapidpro:8000, `/c/`→courier:8080, `/mr/`→mailroom:8090 (`nginx/default.conf`).
- SeaweedFS is the only S3 store: all-in-one `weed server -s3` (image `chrislusf/seaweedfs:4.47`), port 8333 internal only; buckets are created by the one-shot `seaweedfs-init` service. Creds `root`/`tembatemba`.
- Host-published ports (for local debugging): nginx 80, postgres `127.0.0.1:5433`, elastic 9200, redis `127.0.0.1:6380`, rapidpro 8000, mailroom 8090, courier 8080.
- Surveyor constraints: published survey flows must stay `spec_version` ≤ 13.x; the Android app needs HTTPS in the field.

## Node
- The app image installs **Node 20** (`rapidpro/Dockerfile:27`) to run `npm install` so flow-editor/temba-components assets exist for `collectstatic`. Keep Node 20 to match RapidPro CI.
- There is no Node 18 / Puppeteer E2E harness on this branch (the old `test/main.js` and `package.json` are gone); CI installs no Node.
