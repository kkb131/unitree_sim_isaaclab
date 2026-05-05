# Customizations vs Upstream

This fork carries small additions and one upstream-file patch on top of
`unitreerobotics/unitree_sim_isaaclab`. Everything here is meant to be
auditable against the upstream repository so you can rebase / merge cleanly.

Upstream tracked at: <https://github.com/unitreerobotics/unitree_sim_isaaclab>

---

## 1. Modified upstream files

### `auto_setup_env.sh` (1 line change)

Made the openssl certificate generation non-interactive so the installer can
run unattended. Without this patch the script hangs at the cert prompt and
breaks any CI / scripted setup.

```diff
- openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem
+ openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem -subj "/C=US/ST=NA/L=NA/O=Unitree/OU=Sim/CN=localhost"
```

The cert is only used by `xr_teleoperate` for its WebRTC signaling endpoint,
not by the sim's DDS bus, so the subject is cosmetic.

When upstream releases a new version of `auto_setup_env.sh`, re-apply this
single-line patch (or pick a more meaningful subject if needed).

---

## 2. New files (added by us)

### `activate_env.sh`

Sourceable shell helper that:
- activates conda env `unitree_sim_env`,
- exports `OMNI_KIT_ACCEPT_EULA=Y` / `PRIVACY_CONSENT=Y` (Isaac Sim 5.1 hangs without these on first run),
- exports `CYCLONEDDS_HOME` and prepends it to `LD_LIBRARY_PATH`,
- sets `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` and **`ROS_DOMAIN_ID=1`** (the sim hard-codes `ChannelFactoryInitialize(1)`),
- runs `unalias python python3 pip pip3` to defeat `/root/.bashrc`'s Isaac Lab aliases that otherwise route `python` to `/isaac-sim/python.sh` (a non-conda interpreter that doesn't see our pip-installed deps).

Use it with `source activate_env.sh` from any new shell before launching the
sim.

### `run_sim.sh`

Belt-and-suspenders launcher for `sim_main.py` that uses the conda env's
absolute Python path. Robust against any future shell-alias regression:

```bash
exec /root/miniconda3/envs/unitree_sim_env/bin/python sim_main.py "$@"
```

### `cyclonedds.xml`

Fallback CycloneDDS configuration with multicast disabled and unicast
peers. **Not needed** when both the sim and `xr_teleoperate` containers run
on the same host with `--network=host` (default multicast discovery just
works). Activate by `export CYCLONEDDS_URI=file://$(pwd)/cyclonedds.xml`
on both sides if you ever switch to bridge networking or run cross-host.

### `INTEGRATION_FOR_XR_TELEOPERATE.md`

The single source of truth for everything `xr_teleoperate` needs to talk to
this sim: DDS domain, topics, message types, ZMQ camera ports, host IPs,
verification snippets, and a troubleshooting matrix. Hand this file to the
person who owns the `xr_teleoperate` container.

### `REPLICA_SETUP.md`

Replica setup guide for new machines. Covers GPU compatibility (5090 ↔
3080), step-by-step install, and pitfalls.

### `setup_replica.sh`

Idempotent one-shot installer that drives a fresh machine through every
step we hit during the first install: apt deps → Miniconda → conda ToS →
EULA env vars → `auto_setup_env.sh` → smoke test. Re-runnable; skips
already-completed phases.

### `CUSTOMIZATIONS.md`

This file.

---

## 3. Runtime-only modifications (NOT in git)

These happen automatically when `auto_setup_env.sh` runs and target the
`teleimager/` git submodule, so the parent repo doesn't track them:

```bash
# In auto_setup_env.sh:
sed -i 's/type:.*/type: isaacsim/'           teleimager/cam_config_server.yaml
sed -i 's/image_shape:.*/image_shape: [480, 640]/' teleimager/cam_config_server.yaml
```

These switch the camera driver to `isaacsim` and pin the resolution to 480
× 640. They are re-applied every time `auto_setup_env.sh` runs.

---

## 4. Companion repos cloned by `auto_setup_env.sh`

The upstream installer clones three repos into the parent directory
(`/workspace/isaaclab/datasets/`) — these are **not** part of this fork but
are required at runtime:

| Repo | Path after install | Why |
|---|---|---|
| `IsaacLab` | `../IsaacLab` | Cloned fresh and `./isaaclab.sh --install`-ed into the conda env (separate from the system `/workspace/isaaclab` native install) |
| `cyclonedds` | `../cyclonedds` | Built from source for the C library; `CYCLONEDDS_HOME` points here |
| `unitree_sdk2_python` | `../unitree_sdk2_python` | `pip install -e .`-ed for IDL types (`LowState_`, `LowCmd_`, `HandState_`, …) |

Don't add these as submodules of this fork — `auto_setup_env.sh` already
clones them and may pin specific commits as upstream evolves.

---

## 5. `.gitignore` recommendations

Add to your fork's `.gitignore` to avoid committing build artifacts:

```gitignore
# Python bytecode
**/__pycache__/
*.pyc
*.pyo

# Assets fetched at install time
assets/

# Editor / IDE
.vscode/
.idea/
```

The current upstream `.gitignore` already covers most of these, but the
`__pycache__` directories sometimes leak in via `git status` after running
the sim — verify with `git status` before committing.
