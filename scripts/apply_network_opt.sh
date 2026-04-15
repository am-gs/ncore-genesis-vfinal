#!/bin/bash
set -e

echo "=== Applying SOTA network optimizations ==="

# Write sysctl config
sudo tee /etc/sysctl.d/99-ncore-network.conf > /dev/null << 'SYSCTL'
# NCore Network Optimization — April 2026
# Oracle ARM A1: 4 OCPU, 24GB RAM, MTU 9000 backbone

# TCP Buffer Sizes (256MB max — up from 208KB default)
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 262144 268435456
net.ipv4.tcp_wmem = 4096 262144 268435456

# Connection Queue Sizes
net.core.somaxconn = 32768
net.core.netdev_max_backlog = 32768
net.ipv4.tcp_max_syn_backlog = 32768

# TCP Fast Open: 3 = both incoming and outgoing
net.ipv4.tcp_fastopen = 3

# SACK, reuse TIME_WAIT, keepalive
net.ipv4.tcp_sack = 1
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 9

# Local port range for outgoing connections
net.ipv4.ip_local_port_range = 1024 65535

# Window scaling
net.ipv4.tcp_window_scaling = 1

# TCP memory (4GB allocated for sockets)
net.ipv4.tcp_mem = 786432 1048576 4194304

# File descriptors
fs.file-max = 2097152
SYSCTL

# Apply now
sudo sysctl -p /etc/sysctl.d/99-ncore-network.conf 2>&1 | grep -E "error|tcp_rmem|tcp_wmem|somaxconn" | head -10

echo ""
echo "=== Setting Docker MTU to 9000 (match Oracle jumbo frames) ==="
if [ ! -f /etc/docker/daemon.json ] || ! grep -q "mtu" /etc/docker/daemon.json 2>/dev/null; then
    echo '{"mtu": 9000, "dns": ["1.1.1.1", "8.8.8.8"], "log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}' | sudo tee /etc/docker/daemon.json
    echo "Docker daemon.json updated (MTU=9000, Cloudflare DNS, log rotation)"
else
    echo "Docker already configured"
    cat /etc/docker/daemon.json
fi

echo ""
echo "=== File descriptor limits ==="
sudo tee /etc/security/limits.d/99-ncore.conf > /dev/null << 'LIMITS'
* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
LIMITS
echo "FD limits: 1M for all users"

echo ""
echo "=== DNS: Cloudflare 1.1.1.1 + DNS-over-TLS ==="
sudo sed -i 's/#DNS=/DNS=1.1.1.1 1.0.0.1/' /etc/systemd/resolved.conf
sudo sed -i 's/#FallbackDNS=/FallbackDNS=8.8.8.8 8.8.4.4/' /etc/systemd/resolved.conf
sudo sed -i 's/#DNSOverTLS=no/DNSOverTLS=opportunistic/' /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved 2>/dev/null && echo "DNS-over-TLS enabled with Cloudflare" || echo "DNS restart failed"

echo ""
echo "=== Tailscale MTU optimization ==="
# Set Tailscale MTU to match — prevents fragmentation in the WireGuard tunnel
sudo tailscale up --advertise-tags=tag:server 2>/dev/null || true
# Tailscale auto-detects optimal MTU, but we can verify
ip link show tailscale0 | grep mtu

echo ""
echo "=== Verify final settings ==="
sysctl net.core.rmem_max net.ipv4.tcp_fastopen net.core.somaxconn
echo "Docker MTU: $(cat /etc/docker/daemon.json | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"mtu\",\"not set\"))')"
echo "DNS: $(grep ^DNS= /etc/systemd/resolved.conf 2>/dev/null)"
echo ""
echo "DONE. Restart Docker to apply MTU changes:"
echo "  sudo systemctl restart docker"
echo "  (Agent Zero will need restart after Docker restarts)"
