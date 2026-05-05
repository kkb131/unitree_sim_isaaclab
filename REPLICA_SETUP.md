# Replica Setup Guide

This guide reproduces the `unitree_sim_isaaclab` environment on a fresh
machine that already has a working Isaac Sim Docker container (Isaac Lab
base image), so it can drive `xr_teleoperate` over DDS.

Companion docs:
- [CUSTOMIZATIONS.md](CUSTOMIZATIONS.md) — what we changed vs upstream and why
- [INTEGRATION_FOR_XR_TELEOPERATE.md](INTEGRATION_FOR_XR_TELEOPERATE.md) — DDS / topic / port spec for the teleop side
- [activate_env.sh](activate_env.sh) — conda + DDS env activation
- [run_sim.sh](run_sim.sh) — absolute-path-python wrapper to bypass shell aliases

---

## 1. Host Requirements

| Resource | Minimum | Recommended | Notes |
|---|---|---|---|
| GPU | NVIDIA GeForce RTX 3080 / 3090 / 4090 / 5090 | RTX 4090 / 5090 | RTX 5090 (Blackwell) needs CUDA 12.8+ runtime; PyTorch wheel `cu128` covers it |
| VRAM | 12 GB | 24 GB+ | Headless sim ~6 GB; with WebRTC viewport ~10 GB |
| NVIDIA driver | 535+ for CUDA 12.6, **580+ for CUDA 13** | 580.126.09+ | `nvidia-smi` to verify |
| Disk free | 30 GB | 50 GB+ | conda env ~20 GB, assets ~2 GB, IsaacLab clone ~200 MB |
| OS | Ubuntu 20.04 / 22.04 / 24.04 | Ubuntu 24.04 | Container OS |
| Network | `--network=host` recommended | host net | Required for default multicast DDS between sim and xr_teleoperate |

The replica is intended to run **inside an existing Isaac Lab Docker
container** (such as the one launched by `/workspace/isaaclab/docker/container.py`).
That container already provides:
- A native `/isaac-sim` install (we don't use it directly — we install Isaac
  Sim again via pip into a conda env to follow the upstream-supported path)
- `/workspace/isaaclab` (Isaac Lab native install — we don't touch it)
- ROS 2 Jazzy at `/opt/ros/jazzy` (only used for ad-hoc DDS introspection)

If you don't have such a container, start from NVIDIA's
`nvcr.io/nvidia/isaac-sim:5.1.0` image with `--network=host --gpus all`.

## 2. GPU / Isaac Sim Compatibility

| GPU family | Isaac Sim version | PyTorch wheel | Notes |
|---|---|---|---|
| RTX 5090 (Blackwell, sm_120) | **5.1.0** preferred (5.0.0 also OK) | cu128 | Drivers 570+ |
| RTX 4090 / 4080 (Ada, sm_89) | 5.1.0 / 5.0.0 / 4.5.0 | cu128 or cu126 | Tested replica baseline |
| RTX 3090 / 3080 (Ampere, sm_86) | 5.1.0 / 5.0.0 / 4.5.0 | cu126 | Reduce `--enable_cameras` resolution if VRAM tight |
| RTX 2080 Ti (Turing, sm_75) | 4.5.0 only | cu121 | Isaac Sim 5.x dropped some Turing features |
| Older / non-RTX | Not supported | — | RTX (RT cores) required for Isaac Sim |

The default in `setup_replica.sh` is **Isaac Sim 5.1.0 + cu126**, matching
this guide's reference machine (RTX 4090, driver 580). Override with the
script flags `--isaac-sim 5.0` and/or `--cuda cu128` for other configs.

## 3. One-Shot Install

```bash
# 1. Clone this fork (the URL is your customized fork, not upstream)
cd /workspace/isaaclab/datasets
git clone <YOUR_FORK_URL> unitree_sim_isaaclab
cd unitree_sim_isaaclab

# 2. Run the automated installer
chmod +x setup_replica.sh
./setup_replica.sh

# Optional flags:
#   ./setup_replica.sh --isaac-sim 5.0 --cuda cu128
#   ./setup_replica.sh --skip-apt          # if apt deps already installed
#   ./setup_replica.sh --skip-miniconda    # if /root/miniconda3 already exists
# RTX 5090이면: ./setup_replica.sh --isaac-sim 5.1 --cuda cu128
# 또는 (RTX 5090에 더 검증된 경로): ./setup_replica.sh --isaac-sim 5.0 --cuda cu128
```

Total wall-clock time on a 100 Mbps link: **30–60 minutes** (most of it is
PyTorch + Isaac Sim wheel downloads, ~20 GB).

After completion, verify with:

```bash
source ./activate_env.sh
python -c "import isaacsim, torch; print(torch.cuda.get_device_name(0), torch.cuda.is_available())"
./run_sim.sh --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint \
  --enable_dex3_dds --robot_type g129 --headless --no_render \
  --device cuda:0 --enable_cameras
```

A successful run reaches `[DDSManager] manager started, managing 4 publishing
objects` in ~80 s, and `rt/lowstate` publishes at ~94 Hz on DDS domain 1.

## 4. What `setup_replica.sh` Does

Each step is idempotent and the script can be re-run safely:

1. **Pre-flight** — disk, GPU, OS, Docker, conda absence checks
2. **APT deps** — `cmake build-essential openssl git git-lfs unzip ca-certificates curl wget iproute2`
3. **Miniconda** — install to `/root/miniconda3`, init bash, set libmamba solver, accept Anaconda channel ToS
4. **Repo init** — verify cwd is the fork and `git submodule update --init --recursive`
5. **Upstream patches verified** — `auto_setup_env.sh` already contains the openssl `-subj` fix in this fork (see CUSTOMIZATIONS.md)
6. **Run patched `auto_setup_env.sh`** — clones IsaacLab + cyclonedds + unitree_sdk2_python into `..`, fetches assets via git-lfs, builds CycloneDDS from source, creates the conda env `unitree_sim_env`, pip-installs Isaac Sim + PyTorch + IsaacLab + unitree_sdk2_python + teleimager
7. **Post-install patches** — none needed (all custom files are tracked in this fork)
8. **Smoke test** — non-interactive `import` check

If any step fails the script exits with a clear message and you can re-run
it; idempotency means completed steps are skipped.

## 5. Manual Replication (if `setup_replica.sh` fails partway)

```bash
# A. APT deps
apt-get update && apt-get install -y --no-install-recommends \
  cmake build-essential openssl git git-lfs unzip ca-certificates curl wget iproute2
git lfs install

# B. Miniconda
cd /tmp && wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p /root/miniconda3
/root/miniconda3/bin/conda init bash
source /root/.bashrc
/root/miniconda3/bin/conda config --set solver libmamba
/root/miniconda3/bin/conda config --set auto_activate_base false
/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# C. EULA pre-acceptance (sim_main.py would otherwise hang)
echo 'export OMNI_KIT_ACCEPT_EULA=Y' >> /root/.bashrc
echo 'export PRIVACY_CONSENT=Y' >> /root/.bashrc

# D. Submodules + upstream installer
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
git submodule update --init --recursive
bash auto_setup_env.sh 5.1 unitree_sim_env cu126   # adjust args for your GPU
```

## 6. Common Pitfalls (and how `setup_replica.sh` handles them)

| Pitfall | What goes wrong | Mitigation |
|---|---|---|
| **`/root/.bashrc` aliases `python` to `/isaac-sim/python.sh`** | After conda activate, `python sim_main.py` still runs Isaac Sim's bundled Python (no teleimager) → `ModuleNotFoundError: teleimager.image_server` | `activate_env.sh` calls `unalias python python3 pip pip3`; or use `run_sim.sh` (absolute path) |
| **Conda Terms of Service prompt** | `conda create` aborts non-interactively | Pre-accept ToS for `pkgs/main` and `pkgs/r` |
| **OpenSSL cert generation prompt** | `auto_setup_env.sh` hangs at openssl req | Patched to use `-subj "..."` flag (committed in this fork) |
| **NVIDIA Omniverse EULA prompt** | `import isaacsim` hangs reading from stdin | `OMNI_KIT_ACCEPT_EULA=Y`, `PRIVACY_CONSENT=Y` |
| **DDS domain mismatch** | `rt/lowstate` subscriber receives 0 messages | `ROS_DOMAIN_ID=1` (sim hard-codes domain 1), or call `ChannelFactoryInitialize(1)` |
| **`ros2 topic list` empty** | Unitree topics use raw CycloneDDS types, not ROS 2 IDL | Verify with `unitree_sdk2py.ChannelSubscriber` instead |

## 7. Customizations Tracked in this Fork

See [CUSTOMIZATIONS.md](CUSTOMIZATIONS.md) for the full list with rationale.
Summary:
- **Modified**: `auto_setup_env.sh` (openssl `-subj`)
- **Added**: `activate_env.sh`, `run_sim.sh`, `cyclonedds.xml`, `setup_replica.sh`, `INTEGRATION_FOR_XR_TELEOPERATE.md`, `REPLICA_SETUP.md`, `CUSTOMIZATIONS.md`

When upstream releases changes, rebase / merge carefully — the openssl line
in `auto_setup_env.sh` is the only file we touched in upstream territory.

## 8. Uninstall

```bash
# Remove conda env (keeps Miniconda + repo)
conda env remove -n unitree_sim_env

# Remove cloned companion repos and assets
rm -rf /workspace/isaaclab/datasets/{IsaacLab,cyclonedds,unitree_sdk2_python}
rm -rf /workspace/isaaclab/datasets/unitree_sim_isaaclab/assets

# Full clean (also removes Miniconda)
rm -rf /root/miniconda3
# manually edit /root/.bashrc to remove the `>>> conda initialize >>>` block
```

`/isaac-sim` and `/workspace/isaaclab` are untouched by this procedure.
