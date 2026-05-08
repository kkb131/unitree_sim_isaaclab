#!/bin/bash
# Boot wrapper for the UR10e + DG-5F sim.
#
# UR10e is single-arm — there's no `left_wrist_camera` in the scene, so the
# default `teleimager/cam_config_server.yaml` (which publishes all three)
# would crash the image_server when it gets no frames for left_wrist.
# We patch the YAML in-place to disable left_wrist's ZMQ+WebRTC for this run,
# then restore the original on exit (matches the CUSTOMIZATIONS.md note that
# this YAML is treated as runtime-mutable).
#
# Usage:
#     ./custom/scripts/run_ur10e_dg5f.sh [extra sim_main args]
#
# Default args: --task Isaac-Reach-UR10e-DG5F-Joint --robot_type ur10e
#               --enable_dg5f_dds --enable_cameras
#               --camera_include "front_camera,right_wrist_camera"
#               --device cuda:0 --headless

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
YAML="$REPO_ROOT/teleimager/cam_config_server.yaml"
BAK="$YAML.ur10e.bak"

# 1) backup + patch left_wrist_camera section: enable_zmq=false, enable_webrtc=false
cp "$YAML" "$BAK"
python3 - "$YAML" <<'PY'
import sys, re
path = sys.argv[1]
text = open(path).read()
# patch left_wrist_camera block enable_zmq / enable_webrtc to false
pat = re.compile(
    r"(left_wrist_camera:\s*[^#]*?enable_zmq:\s*)true",
    re.DOTALL,
)
text = pat.sub(r"\1false", text, count=1)
pat2 = re.compile(
    r"(left_wrist_camera:\s*[^#]*?enable_webrtc:\s*)true",
    re.DOTALL,
)
text = pat2.sub(r"\1false", text, count=1)
open(path, "w").write(text)
print("[run_ur10e_dg5f] patched left_wrist_camera enable_zmq/webrtc → false")
PY

# 2) restore on exit (any reason)
restore_yaml() {
    if [ -f "$BAK" ]; then
        mv "$BAK" "$YAML"
        echo "[run_ur10e_dg5f] restored original $YAML"
    fi
}
trap restore_yaml EXIT INT TERM

# 3) activate env + launch sim_main with default-or-passed args
# shellcheck source=/dev/null
source "$REPO_ROOT/custom/scripts/activate_env.sh"

DEFAULT_ARGS=(
    --task Isaac-Reach-UR10e-DG5F-Joint
    --robot_type ur10e
    --enable_dg5f_dds
    --enable_cameras
    --camera_include "front_camera,right_wrist_camera"
    --device cuda:0
    --headless
)

cd "$REPO_ROOT"
echo "[run_ur10e_dg5f] launching sim_main..."
python -u sim_main.py "${DEFAULT_ARGS[@]}" "$@"
