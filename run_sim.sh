#!/bin/bash
# Robust launcher for sim_main.py — bypasses any /root/.bashrc python aliases
# by invoking the conda env's python via absolute path. All args are forwarded.
#
# Usage:
#   ./run_sim.sh --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint \
#       --enable_dex3_dds --robot_type g129 --headless --no_render \
#       --device cuda:0 --enable_cameras

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_env.sh"
exec /root/miniforge3/envs/unitree_sim_env/bin/python "$SCRIPT_DIR/sim_main.py" "$@"
