# syntax=docker/dockerfile:1

# nyaruka publishes a prebuilt rp-archiver binary; it is glibc-dynamic, so we keep
# a glibc runtime (distroless/base has glibc + ca-certificates + tzdata, no shell).
FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8 AS tools

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
