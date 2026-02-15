<p align="center">
  <img src="public/geode_logo.png" alt="Geode Logo" width="200"/>
</p>

<h1 align="center">Geode</h1>

<p align="center">
  <strong>A wrapper for Minecraft Bedrock Dedicated Server</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Minecraft-Bedrock%20Edition-green?style=flat" alt="Minecraft Bedrock"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker" alt="Docker Ready"/>
</p>

---

## What is Geode?

Geode wraps the official **Bedrock Dedicated Server**, giving you vanilla gameplay with extensive management features: automatic backups, scheduled restarts, live map rendering, and a REST API for control.

## Features

| Feature                     | Status                |
|-----------------------------|-----------------------|
| Auto-update Bedrock Server  | ✅                     |
| Scheduled automatic backups | ✅                     |
| Cloud storage (GCS, S3)     | ✳️ (GCS only)         |
| Restore backups             | ✅                     |
| Map rendering via Unmined   | ✅                     |
| Scheduled server restarts   | ✅                     |
| REST API for server control | ✅                     |
| Discord relay integration   | 🚧 Under construction |
| Web GUI dashboard           | 🚧 Under construction |
| Player statistics tracking  | 🚧 Under construction |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Google Cloud or AWS account for cloud backups

### Run with Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/geode.git
cd geode

# Create your config file
cp config.default.yml config.yml

# Edit configuration
nano config.yml

# Start the server
docker-compose up -d
```

Geode will automatically download the latest Bedrock Dedicated Server and start it on port `19132`.

### Run with Docker

```bash
# Build the image
docker build -t geode .

# Run with local backups
docker run -d \
  -p 19132:19132/udp \
  -p 19132:19132/tcp \
  -p 8000:8000 \
  -v ./config.yml:/geode/config.yml \
  -v ./server:/server \
  geode

# Run with Google Cloud backups
docker build --build-arg CLOUD_SERVICE=gcloud -t geode:gcloud .
docker run -d \
  -e GOOGLE_APPLICATION_CREDENTIALS=/credentials/keyfile.json \
  -v /path/to/keyfile.json:/credentials/keyfile.json \
  -p 19132:19132/udp \
  -p 8000:8000 \
  geode:gcloud
```

---

## Configuration

### Main Configuration

Edit `config.yml` to configure backups, restarts, Discord relay, and other settings. See `config.default.yml` for all available options.

### Custom Map Rendering

Geode uses [Unmined](https://unmined.net/) for world map rendering. Customize via Docker volumes:

```bash
# Custom map styles (replace entire /map directory)
-v ./my-map-configs:/map

# Custom block styles for rendering
-v ./custom.blockstyles.txt:/unmined/config/custom.blockstyles.txt
```

### Server Properties

Standard Bedrock server files are located in `/server`:
- `server.properties` - Server configuration
- `allowlist.json` - Whitelisted players
- `permissions.json` - Operator permissions

---

## API Reference

> ⚠️ **NEVER expose port 8000 to the internet!**
> 
> The API has no authentication (as of now) and provides full server control. Instead, run a web GUI that connects to port 8000 locally, or place behind a reverse proxy with proper authentication.

### Common Endpoints

```http
GET  /info              # Server status, version, uptime
POST /controls/start    # Start the server
POST /controls/stop     # Stop the server
POST /controls/restart  # Restart the server
GET  /controls/logs     # Live log stream (SSE)
```

Full API documentation available at `/api/docs` when the server is running.

---

## Roadmap
The goal for Geode is to be super easy to install and run. As of now, it is quite involved. There is also currently no GUI to manage your server.

These are *some* future roadmap items, in no particular order:
- [ ] Simple Web GUI dashboard
- [ ] World management
- [ ] Run multiple BDS instances at once
- [ ] Resource & Behaviour Pack management
- [ ] Automated crash recovery improvements
- [ ] Local database for config instead of `config.yml`
- [ ] Server & Geode statistics (Backup times, Server load, etc.)
- [ ] More Cloud Storage options (Google Drive, Dropbox?)
- [ ] Simple, lightweight plugin support (For extensive game management, use Mojang's Scripting API)
- [ ] Automatically update and install [Amethyst](https://github.com/ProtocolPav/amethyst), an addon designed to work together
- [ ] Support for No-[Nexuscore](https://github.com/ProtocolPav/nexuscore)

---

## Acknowledgments

- [Bedrock Dedicated Server](https://www.minecraft.net/en-us/download/server/bedrock) by Mojang
- [Unmined](https://unmined.net/) for map rendering
- [Sanic](https://sanic.readthedocs.io/) async web framework
