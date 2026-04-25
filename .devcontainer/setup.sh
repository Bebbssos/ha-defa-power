#!/usr/bin/env bash
set -e

CONFIG_DIR="/config"

# Ensure the HA config directory exists
mkdir -p "$CONFIG_DIR"

# Write a minimal configuration.yaml if one doesn't exist yet
if [ ! -f "$CONFIG_DIR/configuration.yaml" ]; then
  cat > "$CONFIG_DIR/configuration.yaml" <<'EOF'
# Minimal Home Assistant configuration for development
default_config:

# Enable the frontend
frontend:

# Logger – set defa_power to debug for development
logger:
  default: warning
  logs:
    custom_components.defa_power: debug
EOF
fi

echo "Dev container setup complete."
echo ""
echo "To start Home Assistant:"
echo "  Terminal:  hass -c /config"
echo "  Debugger:  Press F5 in VS Code (Run > Start Debugging)"
echo ""
echo "Then open http://localhost:8123 in your browser."
