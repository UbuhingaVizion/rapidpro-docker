# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# RapidPro webapp image (shared by the rapidpro / celery / celerybeat services).
#
# Multi-stage: the dev toolchain (compilers, -dev headers, npm cache) exists
# only in `builder`; the runtime stage carries the built venv, front-end
# node_modules, source, node + a modern less (for django-compressor's lessc) and
# the shared libraries needed at runtime. The container starts as root only to
# fix the shared `sitestatic` volume, then drops to the unprivileged `temba`
# user (gosu). Base images are pinned by digest.
# ---------------------------------------------------------------------------

# node 22 (the security-updated JS deps require >=22, e.g. postcss-cli 12) - front-end assets
FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS node

# ---- builder: venv + front-end assets ------------------------------------
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS builder

# RapidPro source is fetched at a pinned ref from the UbuhingaVizion fork.
# v9.0.0-ubuviz.5 == branch develop @ 4db65628f (previously .4 @ a978563d8)
ARG RAPIDPRO_REPO=UbuhingaVizion/rapidpro
ARG RAPIDPRO_REF=v9.0.0-ubuviz.5

# Security back-ports for packages the fork's uv.lock pins to a vulnerable release.
# Empty = install exactly the fork's lock (no overrides). Each pin must carry an
# exact version so the image stays reproducible; `uv pip check` validates the
# resolution afterwards. Remove an entry once RAPIDPRO_REF ships it.
#   djangorestframework 3.18.1 -> CVE-2026-114136/114137/114138 (DoS + authz bypass)
#
# NOT patchable here: sqlparse 0.5.5 (CVE-2026-54284/59893/71491/59894/84305)
# cannot go to 0.6.x because smartmin 6.1.0 declares `sqlparse<0.6.0`, and the
# smartmin release that widens that range (6.2.x) drops Django 5.2 support.
# That move belongs to the fork, together with the Django 6 upgrade.
ARG RAPIDPRO_SECURITY_PINS=""

# build deps only (dev headers, compilers). Tests upstream use libgdal-dev etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev gdal-bin \
        libpq-dev \
        libjpeg-dev zlib1g-dev \
        libffi-dev libssl-dev \
        libxml2-dev libxslt1-dev \
        libmagic1 \
        build-essential pkg-config \
        curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# node + npm from the official image (build-time only). The bundled `yarn` is a symlink into
# /opt/yarn-v1.22.22, so bring that across too or the symlink dangles (exit 127).
COPY --from=node /usr/local /usr/local
COPY --from=node /opt/yarn-v1.22.22 /opt/yarn-v1.22.22

# install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /rapidpro
# RapidPro source is fetched at the pinned ref (no sibling checkout needed).
RUN git clone --depth 1 --branch "${RAPIDPRO_REF}" \
        "https://github.com/${RAPIDPRO_REPO}.git" /rapidpro \
    && rm -rf /rapidpro/.git

# Pin the venv to the base image interpreter (and never download a managed
# Python) so the venv stays valid when copied into the runtime stage.
ENV UV_PYTHON_DOWNLOADS=never
RUN uv venv --python /usr/local/bin/python3.12 /rapidpro/.venv
ENV VIRTUAL_ENV=/rapidpro/.venv
ENV PATH="/rapidpro/.venv/bin:$PATH"
# [tool.uv] package = false means uv sync installs dependencies only.
RUN uv sync --frozen --no-dev

# Security back-ports (see RAPIDPRO_SECURITY_PINS above). Installed with the same
# uv manager that built the venv, so no pip/setuptools get added to the image.
RUN if [ -n "${RAPIDPRO_SECURITY_PINS}" ]; then \
        uv pip install --no-cache ${RAPIDPRO_SECURITY_PINS} \
        && uv pip check; \
    fi

# front-end assets (flow-editor, temba-components) are copied out of node_modules
# by collectstatic; dev-only deps (tailwind/postcss/bower) aren't needed. RapidPro
# ships a classic yarn.lock and the node image already bundles yarn (v1), so use it.
RUN yarn install --frozen-lockfile --production --non-interactive

# modern less compiler for django-compressor's {% compress %} tags (the pinned
# package.json less@2.7.1 can't parse modern CSS; upstream installs it globally).
# Installed to a dedicated prefix so it can be copied into the runtime as-is.
# Pinned exactly: an unpinned `npm install -g less` silently changes the image on
# every rebuild, which breaks digest-level reproducibility and CVE tracking.
ARG LESS_VERSION=4.9.1
RUN npm install -g --prefix /opt/less "less@${LESS_VERSION}"

# ---- runtime -------------------------------------------------------------
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime

# runtime shared libraries only - no -dev headers, no node/npm
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal32 libgeos-c1v5 libproj25 \
        libpq5 \
        libjpeg62-turbo zlib1g libffi8 libssl3 \
        libxml2 libxslt1.1 \
        libmagic1 \
        ffmpeg curl ca-certificates gosu \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 temba

# django-compressor runs `lessc` while rendering {% compress %} tags even with
# COMPRESS_ENABLED=False, so node + a modern less are needed at runtime.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /opt/less /opt/less
# less's bin resolves its package via relative imports, so keep it inside the
# package and expose it through a symlink rather than copying the script alone.
RUN ln -sf /opt/less/lib/node_modules/less/bin/lessc /usr/local/bin/lessc

COPY --from=builder /rapidpro /rapidpro
# overlay the docker settings (source ships temba/settings.py as a symlink)
RUN rm -f /rapidpro/temba/settings.py
COPY docker_settings.py /rapidpro/temba/settings.py
COPY entrypoint.sh /rapidpro/entrypoint.sh
RUN chmod +x /rapidpro/entrypoint.sh && chown -R temba:temba /rapidpro

ENV VIRTUAL_ENV=/rapidpro/.venv
ENV PATH="/rapidpro/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /rapidpro
EXPOSE 8000
ENTRYPOINT ["/rapidpro/entrypoint.sh"]
