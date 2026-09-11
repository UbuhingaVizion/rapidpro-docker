FROM golang:1.26-bookworm AS build

ARG COURIER_REF=v7.5.13

WORKDIR /src
RUN git clone --depth 1 --branch "${COURIER_REF}" https://github.com/nyaruka/courier.git .

ENV CGO_ENABLED=0
RUN go build -v -o /out/app github.com/nyaruka/courier/cmd/courier

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /out/app /usr/local/bin/app
CMD ["app"]
