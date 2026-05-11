"""Publish a DG-5F HandCmd_ for a few seconds for round-trip testing.

Usage:
    source custom/scripts/activate_env.sh
    # Old form (single uniform target — only valid for joints whose limits
    # include the target; f1_2 in particular cannot accept positive q):
    python custom/scripts/test_dg5f_pub.py [--q 0.3] [--duration 5.0]

    # Preset that respects every joint's URDF limit:
    python custom/scripts/test_dg5f_pub.py --pose fist  [--duration 5.0]
    python custom/scripts/test_dg5f_pub.py --pose open

DDS index → articulation joint (finger-major, set by action_provider_dds.py):

    DDS [0..3]   → rj_dg_1_{1..4}  (thumb)
    DDS [4..7]   → rj_dg_2_{1..4}  (index)
    DDS [8..11]  → rj_dg_3_{1..4}  (middle)
    DDS [12..15] → rj_dg_4_{1..4}  (ring)
    DDS [16..19] → rj_dg_5_{1..4}  (pinky)

Critical joint-limit gotcha from dg5f_right.urdf — DO NOT send q=0.3 uniformly:

    rj_dg_1_2:        upper=0.0   → flexion is NEGATIVE for this joint
    rj_dg_{2..4}_2:   lower=0.0   → flexion is POSITIVE
    rj_dg_5_1/5_2:    asymmetric  → see FIST_POSE below
"""

import argparse
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_
from unitree_sdk2py.idl.default import (
    unitree_hg_msg_dds__HandCmd_,
    unitree_hg_msg_dds__MotorCmd_,
)

# Comfortable "make a fist" pose. Values picked to stay well within every
# rj_dg_*_* limit from dg5f_right.urdf so the tracking test is unambiguous.
# DDS index layout matches the finger-major mapping above.
FIST_POSE = [
    # thumb f1: 1_1 abduct, 1_2 inward flex (NEGATIVE), 1_3/_4 curl
    0.0, -1.0, 0.5, 0.5,
    # index f2:   _1 spread 0, _2 flex POSITIVE, _3/_4 curl
    0.0, 1.0, 0.5, 0.5,
    # middle f3
    0.0, 1.0, 0.5, 0.5,
    # ring f4
    0.0, 1.0, 0.5, 0.5,
    # pinky f5: 5_1 abduct (0..1.05), 5_2 small flex, _3/_4 curl
    0.5, 0.3, 0.5, 0.5,
]

OPEN_POSE = [0.0] * 20

POSES = {"fist": FIST_POSE, "open": OPEN_POSE}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--pose",
        choices=list(POSES.keys()),
        default=None,
        help="named preset that respects all joint limits (overrides --q)",
    )
    p.add_argument("--q", type=float, default=0.3, help="uniform target [rad] for all 20 motors (legacy)")
    p.add_argument("--kp", type=float, default=80.0)
    p.add_argument("--kd", type=float, default=2.0)
    p.add_argument("--duration", type=float, default=5.0, help="seconds to publish")
    p.add_argument("--rate", type=float, default=20.0, help="publish rate Hz")
    args = p.parse_args()

    if args.pose is not None:
        targets = list(POSES[args.pose])
        label = f"pose={args.pose}"
    else:
        targets = [args.q] * 20
        label = f"q={args.q}"

    ChannelFactoryInitialize(1)
    pub = ChannelPublisher("rt/dg5f/cmd", HandCmd_)
    pub.Init()

    cmd = unitree_hg_msg_dds__HandCmd_()
    # Default factory pre-allocates 7 slots; expand to 20 explicitly.
    cmd.motor_cmd = [unitree_hg_msg_dds__MotorCmd_() for _ in range(20)]
    for i in range(20):
        m = cmd.motor_cmd[i]
        m.mode = 1
        m.q = targets[i]
        m.dq = 0.0
        m.tau = 0.0
        m.kp = args.kp
        m.kd = args.kd

    n = int(args.duration * args.rate)
    period = 1.0 / args.rate
    print(f"publishing {n} HandCmd_ msgs to rt/dg5f/cmd ({label}, kp={args.kp}, kd={args.kd})...")
    for _ in range(n):
        pub.Write(cmd)
        time.sleep(period)
    print("done")


if __name__ == "__main__":
    main()
