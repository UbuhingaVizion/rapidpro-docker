# syntax=docker/dockerfile:1

# nyaruka publishes a prebuilt courier binary; it is glibc-dynamic, so we keep a
# glibc runtime (distroless/base has glibc + ca-certificates + tzdata, no shell).
# static busybox provides a healthcheck client without adding a shell/curl.
FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8 AS tools

# Pinned to the UbuhingaVizion mailroom fork's protocol, not the newest release.
# v9.1.19 is the last Courier that puts org_id in the mailroom task and uses the
# per-event channel task types. v9.1.20 changed the task payload, v9.1.21 collapsed
# channel events into a single type, and v9.3.18 renamed the queue
# (handler -> tasks:handler) — none of which the fork understands.
ARG COURIER_REF=v9.1.19

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl busybox-static \
    && rm -rf /var/lib/apt/lists/* \
    && set -e; \
       ver="${COURIER_REF#v}"; \
       curl -fsSL -o /tmp/app.tgz \
         "https://github.com/nyaruka/courier/releases/download/${COURIER_REF}/courier_${ver}_linux_amd64.tar.gz"; \
       tar -xzf /tmp/app.tgz -C /usr/local/bin courier; \
       chmod +x /usr/local/bin/courier; \
       rm /tmp/app.tgz

FROM gcr.io/distroless/base-debian12@sha256:fabbf1c0c357a3d42550111351daed089b20a2c954df13ee2fcff60602515e84

COPY --from=tools /usr/local/bin/courier /usr/local/bin/courier
COPY --from=tools /bin/busybox /busybox
USER nonroot:nonroot
CMD ["courier"]
