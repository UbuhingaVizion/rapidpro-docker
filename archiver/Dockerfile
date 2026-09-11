FROM golang:1.26-bookworm AS build

ARG ARCHIVER_REF=v7.5.0

WORKDIR /src
RUN git clone --depth 1 --branch "${ARCHIVER_REF}" https://github.com/nyaruka/rp-archiver.git .

ENV CGO_ENABLED=0
RUN go build -v -o /out/app github.com/nyaruka/rp-archiver/cmd/rp-archiver

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /out/app /usr/local/bin/app
CMD ["app"]
