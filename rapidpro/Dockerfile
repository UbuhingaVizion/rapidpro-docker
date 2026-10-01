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

# node 20 (matches RapidPro CI) - used only to install front-end assets
FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS node

# ---- builder: venv + front-end assets ------------------------------------
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS builder

# build deps only (dev headers, compilers). Tests upstream use libgdal-dev etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev gdal-bin \
        libpq-dev \
        libjpeg-dev zlib1g-dev \
        libffi-dev libssl-dev \
        libxml2-dev libxslt1-dev \
        libmagic1 \
        build-essential pkg-config \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# node + npm from the official image (build-time only)
COPY --from=node /usr/local /usr/local

# install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /rapidpro
# RapidPro source is the sibling UbuhingaVizion/rapidpro checkout, passed in as the
# `rapidprosrc` additional build context (see docker-compose.yml).
COPY --from=rapidprosrc . /rapidpro

# Pin the venv to the base image interpreter (and never download a managed
# Python) so the venv stays valid when copied into the runtime stage.
ENV UV_PYTHON_DOWNLOADS=never
RUN uv venv --python /usr/local/bin/python3.12 /rapidpro/.venv
ENV VIRTUAL_ENV=/rapidpro/.venv
ENV PATH="/rapidpro/.venv/bin:$PATH"
# [tool.uv] package = false means uv sync installs dependencies only.
RUN uv sync --frozen --no-dev

# front-end assets (flow-editor, temba-components) are copied out of node_modules
# by collectstatic; dev-only deps (tailwind/postcss/bower) aren't needed. RapidPro
# ships a yarn.lock (classic), so install with yarn rather than npm.
RUN npm install -g yarn@1.22.22 \
    && yarn install --frozen-lockfile --production --non-interactive

# modern less compiler for django-compressor's {% compress %} tags (the pinned
# package.json less@2.7.1 can't parse modern CSS; upstream installs it globally).
# Installed to a dedicated prefix so it can be copied into the runtime as-is.
RUN npm install -g --prefix /opt/less less

# ---- runtime -------------------------------------------------------------
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime

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
