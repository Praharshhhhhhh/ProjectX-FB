#!/bin/bash
set -e

echo "=================================================="
echo "   SetuLink Global Cloud Deployment Script"
echo "=================================================="

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "[!] Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
fi

# Ensure .env.production exists
if [ ! -f .env.production ]; then
    echo "[!] .env.production not found! Copying from sample..."
    cp .env.production.sample .env.production
    echo "[!] IMPORTANT: Please edit .env.production with your Supabase URL, Domain, and ZeroTier API token."
    echo "[!] After editing, run this script again."
    exit 1
fi

echo "[*] Building and starting SetuLink Docker cluster..."
sudo docker compose --env-file .env.production up -d --build

echo ""
echo "=================================================="
echo "[+] SetuLink Deployment Successful! 🚀"
echo "[+] Backend API is running."
echo "[+] Gateway Daemon is running in privileged mode."
echo "[+] Caddy is provisioning free SSL certificates."
echo ""
echo "View logs with: sudo docker compose logs -f"
echo "=================================================="
