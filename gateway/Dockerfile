FROM ubuntu:22.04

# Avoid tzdata interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: Python, WireGuard, ZeroTier, iproute2, iptables
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wireguard-tools \
    iproute2 \
    iptables \
    curl \
    gnupg \
    && curl -s https://install.zerotier.com | bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Create start script to run zerotier in background, then start fastapi
RUN echo '#!/bin/bash\n\
# Start zerotier-one daemon in background\n\
zerotier-one -d\n\
# Give it a second to start up\n\
sleep 2\n\
# Start the Gateway API\n\
exec uvicorn main:app --host 0.0.0.0 --port 8001\n\
' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8001
EXPOSE 51820/udp

# We need NET_ADMIN to manage network interfaces
CMD ["/app/start.sh"]
