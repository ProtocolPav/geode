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

# Create and activate a virtual environment
ENV VENV_PATH=/opt/venv
RUN python3 -m venv $VENV_PATH

# Ensure venv Python/pip are preferred
ENV PATH="$VENV_PATH/bin:$PATH"

# Copy requirements and install into venv
COPY . geode/
RUN pip install --no-cache-dir -r geode/requirements/${CLOUD_SERVICE}.txt

# Expose ports
EXPOSE 19132/tcp
EXPOSE 19132/udp
EXPOSE 19133/tcp
EXPOSE 19133/udp
EXPOSE 8000

# Set environment + workdir
ENV PYTHONPATH="${PYTHONPATH}:/geode/"
ENV CLOUD_SERVICE=${CLOUD_SERVICE}

WORKDIR /geode

CMD ["python3", "-u", "src/webserver.py"]
