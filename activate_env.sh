#!/bin/bash
# Source this file to activate the unitree_sim_isaaclab runtime environment.
#   source activate_env.sh
#
# Sets the conda env, NVIDIA EULA acceptance, CycloneDDS paths, and DDS env vars
# that must match between this sim container and the xr_teleoperate container.

source /root/miniforge3/etc/profile.d/conda.sh
conda activate unitree_sim_env

# /root/.bashrc의 Isaac Lab alias가 conda env의 python을 가로채는 것을 방지
unalias python python3 pip pip3 2>/dev/null || true

# NVIDIA Omniverse / Isaac Sim non-interactive acceptance
export OMNI_KIT_ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y

# CycloneDDS shared library (built from source by auto_setup_env.sh Phase 2)
export CYCLONEDDS_HOME=/workspace/isaaclab/datasets/cyclonedds/install
export LD_LIBRARY_PATH=$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH

# DDS / ROS2 settings — MUST MATCH the xr_teleoperate container
# IMPORTANT: sim_main.py hard-codes ChannelFactoryInitialize(1), so the DDS
# domain id is 1 (NOT 0). xr_teleoperate must also use domain 1 — either via
# ChannelFactoryInitialize(1) or by exporting ROS_DOMAIN_ID=1 in its shell.
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=1

# Optional: pin DDS to a specific NIC via XML config (uncomment fallback if multicast fails)
# export CYCLONEDDS_URI=file:///workspace/isaaclab/datasets/unitree_sim_isaaclab/cyclonedds.xml

echo "[unitree_sim_env] active. Python: $(which python)"
echo "  CYCLONEDDS_HOME=$CYCLONEDDS_HOME"
echo "  ROS_DOMAIN_ID=$ROS_DOMAIN_ID  RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
