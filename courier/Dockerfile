FROM debian:bookworm-slim

ARG COURIER_REF=v7.5.13

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# use the prebuilt release binary (nyaruka publishes these; source builds were
# unreliable on constrained networks)
RUN set -e; \
    ver="${COURIER_REF#v}"; \
    curl -fsSL -o /tmp/app.tgz \
      "https://github.com/nyaruka/courier/releases/download/${COURIER_REF}/courier_${ver}_linux_amd64.tar.gz"; \
    tar -xzf /tmp/app.tgz -C /usr/local/bin courier; \
    rm /tmp/app.tgz

CMD ["courier"]
