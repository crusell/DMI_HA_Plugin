# Home Assistant Development Setup

## Option 1: Docker-based Development (Recommended)

### Prerequisites
- Docker and Docker Compose installed
- Git

### Step 1: Create Development Directory
```bash
mkdir ha-dev
cd ha-dev
```

### Step 2: Create Docker Compose File
Create `docker-compose.yml`:

```yaml
version: '3'
services:
  homeassistant:
    container_name: ha-dev
    image: "ghcr.io/home-assistant/home-assistant:stable"
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    privileged: true
    network_mode: host
    environment:
      - TZ=Europe/Stockholm
```

### Step 3: Create Configuration Directory
```bash
mkdir -p config/custom_components
```

### Step 4: Copy Your Integration
```bash
# From your DMI_HA_Plugin directory
cp -r custom_components/dmi_weather ../ha-dev/config/custom_components/
```

### Step 5: Start Home Assistant
```bash
docker-compose up -d
```

### Step 6: Access Home Assistant
- Open browser to: http://localhost:8123
- Complete initial setup
- Go to Settings → Devices & Services → Add Integration
- Search for "DMI Weather"

## Option 2: Python Virtual Environment

### Prerequisites
- Python 3.11+
- pip

### Step 1: Create Virtual Environment
```bash
python3 -m venv ha-dev-env
source ha-dev-env/bin/activate  # On Windows: ha-dev-env\Scripts\activate
```

### Step 2: Install Home Assistant
```bash
pip install homeassistant
```

### Step 3: Create Configuration Directory
```bash
mkdir -p ~/.homeassistant/custom_components
```

### Step 4: Copy Your Integration
```bash
cp -r custom_components/dmi_weather ~/.homeassistant/custom_components/
```

### Step 5: Start Home Assistant
```bash
hass --open-ui
```

## Option 3: VS Code Dev Container (Advanced)

### Prerequisites
- VS Code with Dev Containers extension
- Docker

### Step 1: Create Dev Container
Create `.devcontainer/devcontainer.json`:

```json
{
  "name": "Home Assistant Development",
  "image": "ghcr.io/home-assistant/home-assistant:stable",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.black-formatter",
        "ms-python.flake8"
      ]
    }
  },
  "mounts": [
    "source=${localWorkspaceFolder}/config,target=/config,type=bind"
  ],
  "forwardPorts": [8123],
  "postCreateCommand": "mkdir -p /config/custom_components"
}
```

## Debugging Tips

### 1. Enable Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.dmi_weather: debug
    homeassistant.components.config: debug
```

### 2. Check Logs
```bash
# Docker
docker-compose logs -f homeassistant

# Python
# Logs appear in terminal where you ran 'hass'
```

### 3. Common Issues
- **Integration not found**: Check file permissions and paths
- **Import errors**: Verify all required files are present
- **Config flow errors**: Check manifest.json and config_flow.py

### 4. Testing Your Integration
1. Start Home Assistant
2. Go to Settings → Devices & Services
3. Click "Add Integration"
4. Search for "DMI Weather"
5. Enter test data:
   - Name: "Test Weather"
   - API Key: "2f0562a7-8444-4889-9ef4-1f0e3a62f609"
   - Latitude: "55.9667"
   - Longitude: "12.7667"

### 5. Development Workflow
1. Make changes to your integration files
2. Restart Home Assistant (or just restart the integration)
3. Test the changes
4. Check logs for errors
5. Repeat

## Quick Start Script

Create `setup-dev.sh`:
```bash
#!/bin/bash
echo "Setting up Home Assistant development environment..."

# Create directories
mkdir -p ha-dev/config/custom_components

# Create docker-compose.yml
cat > ha-dev/docker-compose.yml << 'EOF'
version: '3'
services:
  homeassistant:
    container_name: ha-dev
    image: "ghcr.io/home-assistant/home-assistant:stable"
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    privileged: true
    network_mode: host
    environment:
      - TZ=Europe/Stockholm
EOF

# Copy integration
cp -r custom_components/dmi_weather ha-dev/config/custom_components/

echo "Setup complete! Run: cd ha-dev && docker-compose up -d"
```

Make it executable:
```bash
chmod +x setup-dev.sh
./setup-dev.sh
```
