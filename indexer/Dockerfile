# syntax=docker/dockerfile:1

# nyaruka publishes a prebuilt rp-indexer binary; it is glibc-dynamic, so we keep
# a glibc runtime (distroless/base has glibc + ca-certificates + tzdata, no shell).
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 AS tools

ARG INDEXER_REF=v26.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && set -e; \
       ver="${INDEXER_REF#v}"; \
       curl -fsSL -o /tmp/app.tgz \
         "https://github.com/nyaruka/rp-indexer/releases/download/${INDEXER_REF}/rp-indexer_${ver}_linux_amd64.tar.gz"; \
       tar -xzf /tmp/app.tgz -C /usr/local/bin rp-indexer; \
       chmod +x /usr/local/bin/rp-indexer; \
       rm /tmp/app.tgz

FROM gcr.io/distroless/base-debian12@sha256:fabbf1c0c357a3d42550111351daed089b20a2c954df13ee2fcff60602515e84

COPY --from=tools /usr/local/bin/rp-indexer /usr/local/bin/rp-indexer
USER nonroot:nonroot
CMD ["rp-indexer"]
