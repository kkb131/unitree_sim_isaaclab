#!/bin/bash
# Source this file to activate the unitree_sim_isaaclab venv runtime environment.
#   source activate_env_venv.sh [env_name]
#
# conda-free counterpart of activate_env.sh. Sets venv, NVIDIA EULA acceptance,
# CycloneDDS paths, and DDS env vars that must match the xr_teleoperate container.

ENV_NAME=${1:-unitree_sim_env}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venvs/$ENV_NAME"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Error: venv not found at $VENV_DIR"
    echo "Run: bash auto_setup_env_venv.sh <4.5|5.0|5.1> $ENV_NAME [cuda_ver]"
    return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Prevent any stale shell aliases from intercepting venv interpreters
unalias python python3 pip pip3 2>/dev/null || true

# NVIDIA Omniverse / Isaac Sim non-interactive acceptance
export OMNI_KIT_ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y

# CycloneDDS shared library (built from source by auto_setup_env_venv.sh Phase 2)
export CYCLONEDDS_HOME="$SCRIPT_DIR/../cyclonedds/install"
export LD_LIBRARY_PATH=$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH

# DDS / ROS2 settings — MUST MATCH the xr_teleoperate container
# IMPORTANT: sim_main.py hard-codes ChannelFactoryInitialize(1), so the DDS
# domain id is 1 (NOT 0). xr_teleoperate must also use domain 1 — either via
# ChannelFactoryInitialize(1) or by exporting ROS_DOMAIN_ID=1 in its shell.
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=1

# Optional: pin DDS to a specific NIC via XML config
# export CYCLONEDDS_URI=file:///workspace/isaaclab/datasets/unitree_sim_isaaclab/cyclonedds.xml

echo "[$ENV_NAME] active. Python: $(which python)"
echo "  CYCLONEDDS_HOME=$CYCLONEDDS_HOME"
echo "  ROS_DOMAIN_ID=$ROS_DOMAIN_ID  RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
