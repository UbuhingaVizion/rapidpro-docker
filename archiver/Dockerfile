FROM debian:bookworm-slim

ARG ARCHIVER_REF=v7.5.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# use the prebuilt release binary (nyaruka publishes these; source builds were
# unreliable on constrained networks)
RUN set -e; \
    ver="${ARCHIVER_REF#v}"; \
    curl -fsSL -o /tmp/app.tgz \
      "https://github.com/nyaruka/rp-archiver/releases/download/${ARCHIVER_REF}/rp-archiver_${ver}_linux_amd64.tar.gz"; \
    tar -xzf /tmp/app.tgz -C /usr/local/bin rp-archiver; \
    rm /tmp/app.tgz

CMD ["rp-archiver"]
