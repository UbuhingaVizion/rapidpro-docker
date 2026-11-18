# syntax=docker/dockerfile:1

# Courier is built from the UbuhingaVizion fork on the v9.1.19 protocol line so
# it can carry the TikTok handler. v9.1.19 is the last Courier that puts org_id
# in the mailroom task and uses the per-event channel task types; v9.1.20 changed
# the payload, v9.1.21 collapsed channel events, and v9.3.18 renamed the queue.
FROM golang:1.22-alpine@sha256:1699c10032ca2582ec89a24a1312d986a3f094aed3d5c1147b19880afe40e052 AS build

ARG COURIER_REPO=UbuhingaVizion/courier
ARG COURIER_REF=v9.1.19-ubuviz.1

RUN apk add --no-cache git ca-certificates \
    && git clone --depth 1 --branch "${COURIER_REF}" "https://github.com/${COURIER_REPO}.git" /src

WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /courier ./cmd/courier/main.go

# static busybox provides a healthcheck client without adding a shell/curl
FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc AS tools

RUN apt-get update && apt-get install -y --no-install-recommends \
        busybox-static \
    && rm -rf /var/lib/apt/lists/*

FROM gcr.io/distroless/base-debian12@sha256:fabbf1c0c357a3d42550111351daed089b20a2c954df13ee2fcff60602515e84

COPY --from=build /courier /usr/local/bin/courier
COPY --from=tools /bin/busybox /busybox
USER nonroot:nonroot
CMD ["courier"]
