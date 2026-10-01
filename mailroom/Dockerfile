# syntax=docker/dockerfile:1

# mailroom is built from source with CGO_ENABLED=0, so it is a static binary and
# can run on the minimal Alpine runtime. The source is fetched at a pinned ref
# from the AGPL UbuhingaVizion fork of rapidpro/mailroom; that fork retains the
# Surveyor submission endpoint (POST /mr/surveyor/submit) which BSL
# nyaruka/mailroom dropped in v9.1.10.
FROM golang:1.26-bookworm@sha256:a688600ca24f8a4d3ca77f95b0dd40704a9fc787c826660eb7ba0b641b8b175d AS build

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

FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
RUN apk add --no-cache ca-certificates tzdata curl \
    && adduser -D -u 1000 app

COPY --from=build /out/app /usr/local/bin/app
USER app
CMD ["app"]
