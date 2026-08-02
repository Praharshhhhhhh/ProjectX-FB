#!/bin/sh
set -e

echo "================================================"
echo "    SetuLink Edge Router Installer (Linux)      "
echo "================================================"

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

echo -n "Enter Router Serial Number: "
read SERIAL
echo -n "Enter Router Activation Key: "
read KEY

echo "Installing dependencies..."
if command -v apt-get >/dev/null; then
    apt-get update
    apt-get install -y wireguard-tools python3
elif command -v opkg >/dev/null; then
    opkg update
    opkg install wireguard-tools python3
elif command -v dnf >/dev/null; then
    dnf install -y wireguard-tools python3
else
    echo "Unsupported package manager. Please install wireguard and python3 manually."
fi

echo "Setting up SetuLink directory..."
mkdir -p /etc/setulink
mkdir -p /opt/setulink

cat <<EOF > /etc/setulink/config.json
{
  "serial_number": "$SERIAL",
  "activation_key": "$KEY",
  "api_url": "http://127.0.0.1:8001/api"
}
EOF

echo "Downloading agent..."
# In production, this points to raw github or s3 url
# curl -sL https://raw.githubusercontent.com/.../agent.py -o /opt/setulink/agent.py
# For testing locally, assume the file is copied manually or exists at /opt/setulink/agent.py
if [ ! -f /opt/setulink/agent.py ]; then
    echo "Warning: agent.py not found at /opt/setulink/agent.py. Please copy it there."
fi

echo "Installing systemd service..."
cat <<EOF > /etc/systemd/system/setulink.service
[Unit]
Description=SetuLink Edge Router Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/setulink/agent.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable setulink
# systemctl start setulink

echo "Installation complete!"
echo "Run 'systemctl start setulink' to start the agent once agent.py is in place."
