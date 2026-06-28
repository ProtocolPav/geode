FROM debian:bookworm-slim

ARG CLOUD_SERVICE='local'

# Install Python and required system packages
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
    python3 python3-venv python3-pip \
    openssl \
    findutils \
    libicu-dev libcurl4 libcrypt1 && \
    rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer caching — only re-resolves if these change)
COPY pyproject.toml uv.lock /geode/
COPY nexuscore-client /geode/nexuscore-client

# Install dependencies
RUN if [ "$CLOUD_SERVICE" = "gcloud" ]; then \
        uv sync --frozen --no-dev --project /geode --extra gcloud; \
    else \
        uv sync --frozen --no-dev --project /geode; \
    fi

# Copy requirements and install into venv
COPY . /geode/

# Expose ports
EXPOSE 19132/tcp
EXPOSE 19132/udp
EXPOSE 19133/tcp
EXPOSE 19133/udp
EXPOSE 8000

# Set environment + workdir
ENV PYTHONPATH="${PYTHONPATH}:/geode/"
ENV CLOUD_SERVICE=${CLOUD_SERVICE}

WORKDIR /geode/src

CMD ["uv", "run", "--project", "/geode", "python", "-u", "geode.py"]
