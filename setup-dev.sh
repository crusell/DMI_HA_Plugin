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
echo "Then access Home Assistant at: http://localhost:8123"
