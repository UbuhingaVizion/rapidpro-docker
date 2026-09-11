FROM python:3.12-slim-bookworm

ARG RAPIDPRO_REPO=UbuhingaVizion/rapidpro
ARG RAPIDPRO_TAG=develop
ENV RAPIDPRO_REPO=${RAPIDPRO_REPO}
ENV RAPIDPRO_TAG=${RAPIDPRO_TAG}

# system deps: gdal for Django GIS, ffmpeg for media, libmagic for file detection,
# node/npm for the flow-editor & temba-components static assets, curl/wget for
# fetching the source and for the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev gdal-bin \
        libpq-dev \
        libjpeg-dev zlib1g-dev \
        libffi-dev libssl-dev \
        libxml2-dev libxslt1-dev \
        libmagic1 \
        ffmpeg curl wget ca-certificates \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# use node 20 (matches RapidPro CI) and install the less compiler used by compressor
RUN npm install -g n && n 20 && npm install -g less

WORKDIR /rapidpro
RUN wget -O rapidpro.tar.gz "https://github.com/${RAPIDPRO_REPO}/archive/${RAPIDPRO_TAG}.tar.gz" \
    && tar -xf rapidpro.tar.gz --strip-components=1 \
    && rm rapidpro.tar.gz

# create the venv and install the locked dependency set with uv.
# [tool.uv] package = false means uv sync installs dependencies only, not the project.
RUN uv venv /rapidpro/.venv
ENV VIRTUAL_ENV=/rapidpro/.venv
ENV PATH="/rapidpro/.venv/bin:$PATH"
RUN uv sync --frozen --no-dev

# frontend assets (flow-editor, temba-components) are collected from node_modules by
# collectstatic at container start
RUN npm install

EXPOSE 8000
COPY entrypoint.sh /rapidpro/
COPY docker_settings.py /rapidpro/temba/settings.py
RUN chmod +x /rapidpro/entrypoint.sh
ENTRYPOINT ["/rapidpro/entrypoint.sh"]
