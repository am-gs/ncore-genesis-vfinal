#!/bin/bash
# NCore Genesis vFinal deploy script (Oracle VM)
# Runs from the cloned repo directory and wires up OpenClaw + MoE orchestrator
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NCORE_DIR="${NCORE_DIR:-$SCRIPT_DIR}"

echo "═══════════════════════════════════════════════════════════════"
echo "  NCore Genesis vFinal Deployment (Oracle VM)"
echo "═══════════════════════════════════════════════════════════════"

# --- Phase 0: Base packages & Docker repo ---
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

if [ ! -f /usr/share/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
fi

sudo apt-get update
sudo apt-get install -y \
  clang llvm libbpf-dev linux-headers-"$(uname -r)" \
  libjemalloc2 zram-config irqbalance \
  build-essential python3-pip python3-venv python3-dev \
  docker-ce docker-ce-cli containerd.io docker-compose-plugin \
  ufw git redis-server

sudo systemctl enable --now docker redis-server

# --- Phase 1: Kernel & networking tuning (conservative subset) ---
sudo tee /etc/sysctl.d/99-ncore.conf > /dev/null <<'EOF'
net.core.somaxconn = 8192
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_fin_timeout = 20
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10000 65000
net.core.netdev_max_backlog = 5000
net.core.rmem_default = 134217728
net.core.wmem_default = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
vm.swappiness = 10
vm.dirty_ratio = 20
vm.dirty_background_ratio = 5
EOF
sudo sysctl --system

# --- Phase 2: C-shims (crypt-shredder + TCP_NODELAY) ---
mkdir -p "$NCORE_DIR/libs"

cat > "$NCORE_DIR/libs/crypt_shredder.c" << 'EOF'
#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <malloc.h>

static void (*original_free)(void*) = NULL;

__attribute__((constructor)) static void setup(void) {
    original_free = dlsym(RTLD_NEXT, "free");
}

void free(void *ptr) {
    if (!ptr) return;
    size_t size = malloc_usable_size(ptr);
    if (size > 0) memset(ptr, 0, size);
    if (!original_free) original_free = dlsym(RTLD_NEXT, "free");
    original_free(ptr);
}
EOF

gcc -shared -fPIC "$NCORE_DIR/libs/crypt_shredder.c" -o "$NCORE_DIR/libs/crypt_shredder.so" -ldl

cat > "$NCORE_DIR/libs/force_nodelay.c" << 'EOF'
#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

int socket(int domain, int type, int protocol) {
    int (*original_socket)(int, int, int) = dlsym(RTLD_NEXT, "socket");
    int fd = original_socket(domain, type, protocol);
    if ((domain == AF_INET || domain == AF_INET6) && type == SOCK_STREAM) {
        int flag = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, (char *) &flag, sizeof(int));
    }
    return fd;
}
EOF

gcc -shared -fPIC "$NCORE_DIR/libs/force_nodelay.c" -o "$NCORE_DIR/libs/force_nodelay.so" -ldl

# --- Phase 3: eBPF/XDP firewall ---
cat > "$NCORE_DIR/libs/xdp_stealth.c" << 'EOF'
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <bpf/bpf_helpers.h>

#ifndef bpf_htons
#define bpf_htons(x) __builtin_bswap16(x)
#endif

SEC("xdp_stealth")
int xdp_drop_unauthorized(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if (data + sizeof(*eth) > data_end) return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)ip + sizeof(*ip) > data_end) return XDP_PASS;
    if (ip->protocol != IPPROTO_TCP) return XDP_PASS;

    struct tcphdr *tcp = (void *)ip + ip->ihl * 4;
    if ((void *)tcp + sizeof(*tcp) > data_end) return XDP_PASS;

    if (tcp->syn && !tcp->ack) {
        int port = bpf_htons(tcp->dest);
        if (port != 22 && port != 5678 && port != 8080) {
            return XDP_DROP;
        }
    }
    return XDP_PASS;
}
char _license[] SEC("license") = "GPL";
EOF

clang -O2 -target bpf -c "$NCORE_DIR/libs/xdp_stealth.c" -o "$NCORE_DIR/libs/xdp_stealth.o"
PRIMARY_IFACE=$(ip route | awk '/default/ {print $5; exit}')
if [ -n "$PRIMARY_IFACE" ]; then
  sudo ip link set dev "$PRIMARY_IFACE" xdpgeneric obj "$NCORE_DIR/libs/xdp_stealth.o" sec xdp_stealth || true
fi

# --- Phase 4: Node + OpenClaw + uv/openshell ---
if [ ! -d "$HOME/.nvm" ]; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

nvm install 22
nvm use 22
npm install -g pnpm openclaw@latest

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install -U openshell

# --- Phase 5: Python venv + MoE orchestrator deps ---
python3 -m venv "$NCORE_DIR/core/venv"
"$NCORE_DIR/core/venv/bin/pip" install --upgrade pip
"$NCORE_DIR/core/venv/bin/pip" install -r "$NCORE_DIR/core/requirements.txt"

# --- Phase 6: Firewall & Tailscale (manual auth) ---
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp
yes | sudo ufw enable || true

if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

echo "⚠️  Run 'sudo tailscale up --authkey=YOUR_KEY --ssh' to join tailnet manually."

# --- Phase 7: systemd gateway with MoE orchestrator ---
NODE_VERSION=$(node -v | cut -c2-)
SERVICE_PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v${NODE_VERSION}/bin:$NCORE_DIR/core/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
JEMALLOC_PATH=$(find /usr/lib/aarch64-linux-gnu /usr/lib/x86_64-linux-gnu /usr/lib -name libjemalloc.so.2 -print -quit 2>/dev/null)
if [ -n "$JEMALLOC_PATH" ]; then
  PRELOAD_STRING="$JEMALLOC_PATH:$NCORE_DIR/libs/force_nodelay.so:$NCORE_DIR/libs/crypt_shredder.so"
else
  PRELOAD_STRING="$NCORE_DIR/libs/force_nodelay.so:$NCORE_DIR/libs/crypt_shredder.so"
fi

sudo tee /etc/systemd/system/ncore-gateway.service > /dev/null <<EOF
[Unit]
Description=NCore Genesis vFinal Gateway
After=network.target docker.service tailscaled.service

[Service]
Type=simple
User=$USER
Environment="PATH=$SERVICE_PATH"
Environment="NODE_OPTIONS=--max-old-space-size=16384"
Environment="UV_USE_IO_URING=1"
Environment="LD_PRELOAD=$PRELOAD_STRING"
WorkingDirectory=$NCORE_DIR
ExecStart=$NCORE_DIR/core/venv/bin/python -m uvicorn orchestrator:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=1
LimitNOFILE=2097152
LimitMEMLOCK=infinity
OOMScoreAdjust=-1000
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99
CPUAffinity=2 3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ncore-gateway

echo "═══════════════════════════════════════════════════════════════"
echo "✅ NCore Genesis vFinal deployed."
echo "   - Gateway: http://127.0.0.1:8080"
echo "   - Edit env/keys in $NCORE_DIR/.env as needed."
echo "   - Join Tailscale manually for remote access."
echo "═══════════════════════════════════════════════════════════════"
