#!/bin/bash
# NCore Genesis vFinal — Singularity Deploy Script
# QC-Final: xdpdrv w/ xdpgeneric fallback, CPUAffinity=2, OMP pins,
#           SupplementaryGroups=redis, MALLOC_CONF jemalloc tuning.
# Target: Oracle VM (Ubuntu 22.04+, x86_64 or ARM64)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NCORE_DIR="${NCORE_DIR:-$SCRIPT_DIR}"

echo "================================================================"
echo "  NCore Genesis vFinal — QC-Final Deployment"
echo "================================================================"

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
  libopenblas-dev liblapack-dev libnuma-dev \
  docker-ce docker-ce-cli containerd.io docker-compose-plugin \
  git redis-server

sudo systemctl enable --now docker redis-server

# --- Phase 1: Kernel & networking tuning ---
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

cat > "$NCORE_DIR/libs/crypt_shredder.c" <<'EOF'
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

cat > "$NCORE_DIR/libs/force_nodelay.c" <<'EOF'
#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
int socket(int domain, int type, int protocol) {
    int (*orig)(int, int, int) = dlsym(RTLD_NEXT, "socket");
    int fd = orig(domain, type, protocol);
    if ((domain == AF_INET || domain == AF_INET6) && type == SOCK_STREAM) {
        int flag = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, (char *)&flag, sizeof(int));
    }
    return fd;
}
EOF
gcc -shared -fPIC "$NCORE_DIR/libs/force_nodelay.c" -o "$NCORE_DIR/libs/force_nodelay.so" -ldl

# --- Phase 3: eBPF/XDP firewall ---
# QC FIX: attempt xdpdrv (native, pre-skb-allocation) first;
# fall back to xdpgeneric only if the NIC driver does not support native XDP
# (common on cloud virtio NICs such as Oracle VMs).
cat > "$NCORE_DIR/libs/xdp_stealth.c" <<'EOF'
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
    void *data     = (void *)(long)ctx->data;
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
        if (port != 22 && port != 5678 && port != 8080)
            return XDP_DROP;
    }
    return XDP_PASS;
}
char _license[] SEC("license") = "GPL";
EOF
clang -O2 -target bpf -c "$NCORE_DIR/libs/xdp_stealth.c" -o "$NCORE_DIR/libs/xdp_stealth.o"

PRIMARY_IFACE=$(ip route | awk '/default/ {print $5; exit}')
if [ -n "$PRIMARY_IFACE" ]; then
  # Strip any existing XDP program first
  sudo ip link set dev "$PRIMARY_IFACE" xdpgeneric off 2>/dev/null || true
  sudo ip link set dev "$PRIMARY_IFACE" xdpdrv    off 2>/dev/null || true

  # Try native (pre-skb-allocation) first, fall back to generic
  if sudo ip link set dev "$PRIMARY_IFACE" xdpdrv \
       obj "$NCORE_DIR/libs/xdp_stealth.o" sec xdp_stealth 2>/dev/null; then
    echo "[OK] XDP attached: xdpdrv (native) on $PRIMARY_IFACE"
  else
    sudo ip link set dev "$PRIMARY_IFACE" xdpgeneric \
      obj "$NCORE_DIR/libs/xdp_stealth.o" sec xdp_stealth || true
    echo "[WARN] xdpdrv unsupported on $PRIMARY_IFACE NIC driver, using xdpgeneric"
  fi
fi

# --- Phase 4: Node + OpenClaw + uv/openshell ---
[ ! -d "$HOME/.nvm" ] && \
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install 22 && nvm use 22
npm install -g pnpm openclaw@latest
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install -U openshell

# --- Phase 4.5: Redis Unix Domain Socket ---
sudo mkdir -p /var/run/redis
sudo chown redis:redis /var/run/redis
if ! grep -q '^unixsocket /var/run/redis/redis-server.sock' /etc/redis/redis.conf; then
  printf '\n# NCore Genesis - Unix Domain Socket\nunixsocket /var/run/redis/redis-server.sock\nunixsocketperm 770\n' \
    | sudo tee -a /etc/redis/redis.conf > /dev/null
fi
sudo usermod -aG redis "$USER" || true
sudo systemctl restart redis-server
for i in $(seq 1 10); do
  [ -S /var/run/redis/redis-server.sock ] && break
  sleep 1
done
if [ ! -S /var/run/redis/redis-server.sock ]; then
  echo "ERROR: Redis Unix socket not created — check /etc/redis/redis.conf"
  exit 1
fi
echo "[OK] Redis UDS ready: /var/run/redis/redis-server.sock"

# --- Phase 5: Python venv + Singularity deps ---
python3 -m venv "$NCORE_DIR/core/venv"
"$NCORE_DIR/core/venv/bin/pip" install --upgrade pip wheel setuptools
"$NCORE_DIR/core/venv/bin/pip" install -r "$NCORE_DIR/core/requirements.txt"

# --- Phase 5.5: Critical import verification ---
"$NCORE_DIR/core/venv/bin/python" - <<'PYEOF'
try:
    import uvloop, orjson, numpy, faiss, httpx, redis
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    print("[OK] NCore Python dependency check passed")
except ImportError as e:
    print(f"[FAIL] Missing dependency: {e}")
    raise SystemExit(1)
PYEOF

# --- Phase 6: Tailscale ---
command -v tailscale >/dev/null 2>&1 || curl -fsSL https://tailscale.com/install.sh | sh
echo "[NOTE] Run: sudo tailscale up --authkey=YOUR_KEY --ssh"

# --- Phase 7: systemd gateway ---
NODE_VERSION=$(node -v | cut -c2-)
SERVICE_PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v${NODE_VERSION}/bin:$NCORE_DIR/core/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

JEMALLOC_PATH=$(find \
  /usr/lib/aarch64-linux-gnu \
  /usr/lib/x86_64-linux-gnu \
  /usr/lib \
  -name libjemalloc.so.2 -print -quit 2>/dev/null || true)
if [ -n "$JEMALLOC_PATH" ]; then
  PRELOAD_STRING="${JEMALLOC_PATH}:${NCORE_DIR}/libs/force_nodelay.so"
else
  PRELOAD_STRING="${NCORE_DIR}/libs/force_nodelay.so"
fi

sudo tee /etc/systemd/system/ncore-gateway.service > /dev/null <<EOF
[Unit]
Description=NCore Genesis vFinal - QC-Final Gateway
After=network.target docker.service redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=$USER
# QC FIX: explicit redis group membership so UDS socket is always readable
SupplementaryGroups=redis
Environment="PATH=$SERVICE_PATH"
Environment="NODE_OPTIONS=--max-old-space-size=16384"
Environment="UV_USE_IO_URING=1"
Environment="LD_PRELOAD=$PRELOAD_STRING"
Environment="NCORE_REDIS_UDS=/var/run/redis/redis-server.sock"
# QC FIX: jemalloc background decay tuning — reduces RSS spikes under load
Environment="MALLOC_CONF=background_thread:true,metadata_thp:auto,dirty_decay_ms:50,muzzy_decay_ms:50"
# QC FIX: pin ONNX Runtime and OpenBLAS thread pools to exactly one thread
# so they don't compete with the event loop on the pinned core
Environment="OMP_NUM_THREADS=1"
Environment="OPENBLAS_NUM_THREADS=1"
Environment="MKL_NUM_THREADS=1"
WorkingDirectory=$NCORE_DIR/core
ExecStart=$NCORE_DIR/core/venv/bin/python -m uvicorn orchestrator:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=2
LimitNOFILE=2097152
LimitMEMLOCK=infinity
OOMScoreAdjust=-1000
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99
# QC FIX: single core pin for L1/L2 cache locality on the event loop;
# OMP/OpenBLAS/MKL are already restricted to 1 thread above so no
# internal thread pool is silently pinned to the same core.
CPUAffinity=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ncore-gateway

echo "================================================================"
echo " NCore Genesis vFinal - QC-Final Singularity Layer deployed."
echo "  Gateway : http://127.0.0.1:8080"
echo "  Metrics : http://127.0.0.1:8080/metrics"
echo "  Health  : http://127.0.0.1:8080/health"
echo "  Redis   : /var/run/redis/redis-server.sock"
echo "  Logs    : journalctl -u ncore-gateway -f"
echo "================================================================"
