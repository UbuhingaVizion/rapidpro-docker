# syntax=docker/dockerfile:1

# nyaruka publishes a prebuilt rp-archiver binary; it is glibc-dynamic, so we keep
# a glibc runtime (distroless/base has glibc + ca-certificates + tzdata, no shell).
FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251 AS tools

ARG ARCHIVER_REF=v26.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && set -e; \
       ver="${ARCHIVER_REF#v}"; \
       curl -fsSL -o /tmp/app.tgz \
         "https://github.com/nyaruka/rp-archiver/releases/download/${ARCHIVER_REF}/rp-archiver_${ver}_linux_amd64.tar.gz"; \
       tar -xzf /tmp/app.tgz -C /usr/local/bin rp-archiver; \
       chmod +x /usr/local/bin/rp-archiver; \
       rm /tmp/app.tgz

FROM gcr.io/distroless/base-debian12@sha256:fabbf1c0c357a3d42550111351daed089b20a2c954df13ee2fcff60602515e84

COPY --from=tools /usr/local/bin/rp-archiver /usr/local/bin/rp-archiver
USER nonroot:nonroot
CMD ["rp-archiver"]
