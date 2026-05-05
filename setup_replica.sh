#!/bin/bash
# setup_replica.sh — one-shot replica installer for unitree_sim_isaaclab.
# Idempotent: safe to re-run after partial failures.
#
# Usage:
#   ./setup_replica.sh                              # default: Isaac Sim 5.1, cu126
#   ./setup_replica.sh --isaac-sim 5.0 --cuda cu128 # for RTX 5090 alt path
#   ./setup_replica.sh --skip-apt --skip-miniconda  # if already done
#
# See REPLICA_SETUP.md for full context.

set -e
set -o pipefail

# ---------- defaults ----------
ISAAC_VERSION="5.1"
CUDA_VER="cu126"
ENV_NAME="unitree_sim_env"
SKIP_APT=0
SKIP_MINICONDA=0
SKIP_AUTOSETUP=0
SKIP_SMOKE=0

# ---------- arg parsing ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --isaac-sim)     ISAAC_VERSION="$2"; shift 2 ;;
        --cuda)          CUDA_VER="$2"; shift 2 ;;
        --env-name)      ENV_NAME="$2"; shift 2 ;;
        --skip-apt)      SKIP_APT=1; shift ;;
        --skip-miniconda) SKIP_MINICONDA=1; shift ;;
        --skip-autosetup) SKIP_AUTOSETUP=1; shift ;;
        --skip-smoke)    SKIP_SMOKE=1; shift ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo "unknown arg: $1"; exit 1 ;;
    esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

log()  { echo -e "\n\033[1;36m[replica]\033[0m $*"; }
warn() { echo -e "\033[1;33m[replica:warn]\033[0m $*" >&2; }
fail() { echo -e "\033[1;31m[replica:fail]\033[0m $*" >&2; exit 1; }

# ---------- 1. pre-flight ----------
log "1/8 pre-flight checks"
command -v nvidia-smi >/dev/null || fail "nvidia-smi not found — need a CUDA-capable host"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits | head -1
DISK_FREE_GB=$(df -BG /root | awk 'NR==2 {gsub("G","",$4); print $4}')
[ "$DISK_FREE_GB" -lt 30 ] && fail "need ≥30 GB free on /root, got ${DISK_FREE_GB}G"
log "  disk free: ${DISK_FREE_GB}G OK"
[ -f /etc/os-release ] && . /etc/os-release && log "  OS: $PRETTY_NAME"
[ -f auto_setup_env.sh ] || fail "must run from repo root (auto_setup_env.sh missing)"
[ -f teleimager/pyproject.toml ] || warn "teleimager submodule not initialized — will fix in step 4"

# ---------- 2. apt deps ----------
if [ "$SKIP_APT" -eq 0 ]; then
    log "2/8 installing apt deps (cmake, git-lfs, iproute2, …)"
    apt-get update
    apt-get install -y --no-install-recommends \
        cmake build-essential openssl git git-lfs unzip \
        ca-certificates curl wget iproute2
    git lfs install
else
    log "2/8 skipped (--skip-apt)"
fi

# ---------- 3. miniconda ----------
if [ "$SKIP_MINICONDA" -eq 0 ]; then
    if [ ! -x /root/miniconda3/bin/conda ]; then
        log "3/8 installing Miniconda → /root/miniconda3"
        cd /tmp
        wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
        bash miniconda.sh -b -p /root/miniconda3
        cd "$REPO_DIR"
        /root/miniconda3/bin/conda init bash
    else
        log "3/8 Miniconda already at /root/miniconda3 — skipping install"
    fi
    /root/miniconda3/bin/conda config --set solver libmamba
    /root/miniconda3/bin/conda config --set auto_activate_base false
    log "  accepting Anaconda channel ToS"
    /root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
    /root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
else
    log "3/8 skipped (--skip-miniconda)"
fi

# ---------- 4. submodules ----------
log "4/8 initializing git submodules"
git submodule update --init --recursive

# ---------- 5. EULA pre-acceptance ----------
log "5/8 ensuring NVIDIA EULA env vars are set in /root/.bashrc"
grep -q "OMNI_KIT_ACCEPT_EULA" /root/.bashrc || \
    echo 'export OMNI_KIT_ACCEPT_EULA=Y' >> /root/.bashrc
grep -q "PRIVACY_CONSENT" /root/.bashrc || \
    echo 'export PRIVACY_CONSENT=Y'      >> /root/.bashrc
export OMNI_KIT_ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y

# ---------- 6. run upstream installer (already patched in this fork) ----------
if [ "$SKIP_AUTOSETUP" -eq 0 ]; then
    log "6/8 running patched auto_setup_env.sh ${ISAAC_VERSION} ${ENV_NAME} ${CUDA_VER}"
    log "  this is the long step — expect 30–60 minutes"
    grep -q '\-subj' auto_setup_env.sh || warn "auto_setup_env.sh does not contain the openssl -subj patch — see CUSTOMIZATIONS.md"
    bash auto_setup_env.sh "$ISAAC_VERSION" "$ENV_NAME" "$CUDA_VER"
else
    log "6/8 skipped (--skip-autosetup)"
fi

# ---------- 7. activation helper sanity ----------
log "7/8 verifying activate_env.sh wires conda + DDS domain 1"
[ -f activate_env.sh ] || fail "activate_env.sh missing — re-pull this fork"
chmod +x activate_env.sh run_sim.sh 2>/dev/null || true

# ---------- 8. smoke test ----------
if [ "$SKIP_SMOKE" -eq 0 ]; then
    log "8/8 smoke test: import all critical modules"
    # Use absolute python path to bypass any /root/.bashrc alias
    PY=/root/miniconda3/envs/${ENV_NAME}/bin/python
    OMNI_KIT_ACCEPT_EULA=Y PRIVACY_CONSENT=Y "$PY" - <<'PY'
import importlib, sys
mods = ["isaacsim", "torch", "isaaclab", "unitree_sdk2py", "cyclonedds",
        "teleimager", "teleimager.image_server", "gymnasium", "zmq"]
for m in mods:
    try:
        importlib.import_module(m); print(f"  OK  {m}")
    except Exception as e:
        print(f"  FAIL  {m}  →  {type(e).__name__}: {e}")
        sys.exit(1)
import torch
print(f"\nCUDA: {torch.cuda.is_available()}, device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}")
PY
else
    log "8/8 skipped (--skip-smoke)"
fi

cat <<EOF

\033[1;32m===============================================
 Replica setup complete.
===============================================\033[0m

To run the simulator:

    source ${REPO_DIR}/activate_env.sh
    cd ${REPO_DIR}
    python sim_main.py --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint \\
        --enable_dex3_dds --robot_type g129 --device cuda:0 \\
        --enable_cameras --headless --no_render

For xr_teleoperate integration details:
    cat INTEGRATION_FOR_XR_TELEOPERATE.md

To uninstall: see REPLICA_SETUP.md §8.
EOF
