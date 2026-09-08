# 🐳 RapidPro Docker — surveyor-modern

Docker compose for a **Surveyor-capable RapidPro stack** pinned to the last release train that
supports the offline [RapidPro Surveyor](https://github.com/rapidpro/surveyor) Android client.

> ⚠️ This branch is deliberately **not** the latest RapidPro. Upstream removed Surveyor support in
> Mailroom `v9.1.10` (2024-02-23). This branch pins the stack before that cutoff.

## Version locks

| Service | Version | Why |
|---|---|---|
| RapidPro (webapp + celery) | `v7.4.2` | surveyor-era API v2 + `role=S`, flow spec ≤13.x |
| Mailroom | `v9.1.9` | last release serving `POST /mr/surveyor/submit` |
| Courier | `v9.1.9` | era-matched |
| rp-indexer | `v9.1.9` | era-matched |
| Elasticsearch | `7.17.20` | RapidPro 7.4 uses ES7 (ES8 deferred) |
| nginx | latest | routes `/mr/` → mailroom |

Includes: RapidPro webapp + celery, Mailroom, Courier, Indexer, nginx, PostgreSQL (postgis), Redis,
Minio (S3 emulator).

These containers are for development/test use; hardening for production is handled in later stages.

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

## Gotchas (first build)

- Building RapidPro 7.4.2 with Poetry on Python 3.11 may need a Rust toolchain if
  `cryptography 3.4.7` has no wheel for this Python (`apt-get install -y rustc cargo`, or drop the
  base image to `python:3.9-bullseye` for the baseline). Stage 1 moves the image to uv + Python 3.12.
- Keep published survey flows at `spec_version` ≤ 13.x so the phone's embedded engine can run them.
- The Android app (this branch's counterpart) expects HTTPS in the field; HTTP above is for local testing.
