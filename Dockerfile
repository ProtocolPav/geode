FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG CLOUD_SERVICE='local'

## Install required system packages
#RUN apt-get update && \
#    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
#    openssl \
#    findutils \
#    libicu-dev libcurl4 libcrypt1 && \
#    rm -rf /var/lib/apt/lists/*

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
ENV UV_LINK_MODE=copy

WORKDIR /geode

CMD ["uv", "run", "--project", "/geode", "python", "-u", "./src/webserver.py"]
