FROM debian:bookworm-slim

ARG INDEXER_REF=v7.4.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# use the prebuilt release binary (nyaruka publishes these; source builds were
# unreliable on constrained networks)
RUN set -e; \
    ver="${INDEXER_REF#v}"; \
    curl -fsSL -o /tmp/app.tgz \
      "https://github.com/nyaruka/rp-indexer/releases/download/${INDEXER_REF}/rp-indexer_${ver}_linux_amd64.tar.gz"; \
    tar -xzf /tmp/app.tgz -C /usr/local/bin rp-indexer; \
    rm /tmp/app.tgz

CMD ["rp-indexer"]
