# syntax=docker/dockerfile:1

# mailroom is built from source with CGO_ENABLED=0, so it is a static binary and
# can run on the minimal Alpine runtime. The source is fetched at a pinned ref
# from the AGPL UbuhingaVizion fork of rapidpro/mailroom; that fork retains the
# Surveyor submission endpoint (POST /mr/surveyor/submit) which BSL
# nyaruka/mailroom dropped in v9.1.10.
FROM golang:1.26-bookworm@sha256:dc40a13b61304647ed7e5d581d246b86413dfc29d63c6d018310feb93cd98fc0 AS build

# v9.0.0-ubuviz.1 == branch master @ f5a174684b8573d1fafc5df760c2abe8728efd10
ARG MAILROOM_REPO=UbuhingaVizion/mailroom
ARG MAILROOM_REF=v9.0.0-ubuviz.1

WORKDIR /src
RUN git clone --depth 1 --branch "${MAILROOM_REF}" \
        "https://github.com/${MAILROOM_REPO}.git" /src \
    && rm -rf /src/.git

ENV CGO_ENABLED=0
ENV GOPROXY=https://goproxy.io,direct
RUN for i in 1 2 3 4 5; do go build -v -o /out/app github.com/nyaruka/mailroom/cmd/mailroom && break || sleep 10; done

# Editor/expression docs served by mailroom at GET /mr/docs/<lang>/{editor.json,completion.txt,md/...}
# (web/docs/docs.go serves http.Dir("docs"), relative to the process CWD). They are NOT in the
# mailroom repo: upstream downloads the docs tarball published with the matching goflow release,
# so resolve the pinned goflow version from go.mod (e.g. v0.198.0) and fetch the same tarball.
RUN ver="$(grep 'github.com/nyaruka/goflow' go.mod | awk '{print $2}' | sed 's/^v//')" \
    && echo "goflow docs version: ${ver}" \
    && curl -fsSL "https://github.com/nyaruka/goflow/releases/download/v${ver}/docs.tar.gz" | tar -xz \
    && test -f /src/docs/en-us/editor.json

# Alpine 3.23: 3.20 reached end-of-life on 2026-04-01, so it stopped receiving
# security fixes for ca-certificates/tzdata/curl (the runtime's only packages).
FROM alpine:3.23@sha256:469c9ea410b9215eaee7976ba6c0639039b444be8e5d638f7abbada189971eb2
RUN apk add --no-cache ca-certificates tzdata curl \
    && adduser -D -u 1000 app

COPY --from=build /out/app /usr/local/bin/app
# CWD is / (no WORKDIR) so http.Dir("docs") resolves to /docs
COPY --from=build /src/docs /docs
USER app
CMD ["app"]
