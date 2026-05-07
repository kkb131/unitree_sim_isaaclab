#!/bin/bash
# Build UR10e + Tesollo DG-5F (right) integrated URDF + USD assets for IsaacSim.
#
# Output:
#   assets/robots/ur10e-dg5f-urdf/{ur10e,dg5f_right,ur10e_with_dg5f}.urdf
#   assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd (+ configuration/*)
#
# Prereqs (this docker):
#   - ros-jazzy-ur-description, ros-jazzy-xacro (apt installed)
#   - DG-5F sources (default: /workspace/isaaclab/datasets/teleop_system/models/dg5f)
#   - IsaacLab repo (default: /workspace/isaaclab/datasets/IsaacLab)
#   - unitree_sim_env conda env (already activated by activate_env.sh)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
URDF_DIR="$REPO_ROOT/assets/robots/ur10e-dg5f-urdf"
USD_DIR="$REPO_ROOT/assets/robots/ur10e-dg5f-usd"
DG5F_SRC="${DG5F_SRC:-/workspace/isaaclab/datasets/teleop_system/models/dg5f}"
ISAACLAB_ROOT="${ISAACLAB_ROOT:-/workspace/isaaclab/datasets/IsaacLab}"

mkdir -p "$URDF_DIR" "$USD_DIR"

echo "[1/4] Compiling UR10e URDF from ur_description xacro"
# /opt/ros/jazzy/setup.bash references AMENT_TRACE_SETUP_FILES etc. unguarded —
# temporarily relax `set -u` while sourcing ROS env.
set +u
source /opt/ros/jazzy/setup.bash
set -u
xacro /opt/ros/jazzy/share/ur_description/urdf/ur.urdf.xacro \
    name:=ur10e ur_type:=ur10e force_abs_paths:=true \
    > "$URDF_DIR/ur10e.urdf"

echo "[2/4] Sanitizing DG-5F URDF mesh paths (package:// → file://)"
[ -f "$DG5F_SRC/dg5f_right.urdf" ] || { echo "missing $DG5F_SRC/dg5f_right.urdf"; exit 1; }
sed "s|package://dg_description/meshes/|file://${DG5F_SRC}/meshes/|g" \
    "$DG5F_SRC/dg5f_right.urdf" > "$URDF_DIR/dg5f_right.urdf"

echo "[3/4] Combining into single articulation"
python3 "$REPO_ROOT/custom/tools/combine_ur10e_dg5f_urdfs.py" \
    --ur10e "$URDF_DIR/ur10e.urdf" \
    --dg5f "$URDF_DIR/dg5f_right.urdf" \
    --out "$URDF_DIR/ur10e_with_dg5f.urdf"

if [ "${SKIP_USD:-0}" = "1" ]; then
    echo "[4/4] SKIP_USD=1 — skipping URDF → USD conversion"
    echo "[done] URDF only: $URDF_DIR/ur10e_with_dg5f.urdf"
else
    echo "[4/4] Converting URDF → USD via IsaacLab convert_urdf.py"
    python "$ISAACLAB_ROOT/scripts/tools/convert_urdf.py" \
        "$URDF_DIR/ur10e_with_dg5f.urdf" \
        "$USD_DIR/ur10e_with_dg5f.usd" \
        --merge-joints --fix-base \
        --joint-stiffness 100.0 --joint-damping 2.0 \
        --headless
    echo "[done] USD: $USD_DIR/ur10e_with_dg5f.usd"
fi
