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

# 2) restore on exit + forward Ctrl+C / SIGTERM to the python child. Without
# the manual forward, bash holds SIGINT and the python child keeps running
# until killed manually. Launching python in the background + `wait` lets us
# observe the signal here, kill the child explicitly, and still let the EXIT
# trap restore the yaml.
SIM_PID=""
RC=0

restore_yaml() {
    if [ -f "$BAK" ]; then
        mv "$BAK" "$YAML"
        echo "[run_ur10e_dg5f] restored original $YAML"
    fi
}

forward_sig() {
    sig="$1"
    if [ -n "$SIM_PID" ] && kill -0 "$SIM_PID" 2>/dev/null; then
        echo "[run_ur10e_dg5f] forwarding SIG${sig} → sim_main (pid=$SIM_PID)"
        kill -"$sig" "$SIM_PID" 2>/dev/null || true
    fi
}

trap 'forward_sig INT'  INT
trap 'forward_sig TERM' TERM
trap restore_yaml EXIT

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
    # --headless
)

cd "$REPO_ROOT"
echo "[run_ur10e_dg5f] launching sim_main... (Ctrl+C to stop)"
# `set -e` would abort on the first non-zero `wait`; disable it for the wait loop.
set +e
python -u sim_main.py "${DEFAULT_ARGS[@]}" "$@" &
SIM_PID=$!
# wait returns 128+sig on signal; loop until the child actually exits so the
# forwarded INT/TERM gets a chance to land before we leave the wait.
while kill -0 "$SIM_PID" 2>/dev/null; do
    wait "$SIM_PID"
    RC=$?
done
set -e
exit "$RC"
