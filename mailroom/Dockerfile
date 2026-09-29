FROM golang:1.26-bookworm AS build

ARG MAILROOM_REF=v7.5.13

WORKDIR /src
RUN git clone --depth 1 --branch "${MAILROOM_REF}" https://github.com/nyaruka/mailroom.git .

ENV CGO_ENABLED=0
ENV GOPROXY=https://goproxy.io,direct
RUN for i in 1 2 3 4 5; do go build -v -o /out/app github.com/nyaruka/mailroom/cmd/mailroom && break || sleep 10; done

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /out/app /usr/local/bin/app
CMD ["app"]
