"""Publish a constant DG-5F HandCmd_ for a few seconds for round-trip testing.

Usage:
    source custom/scripts/activate_env.sh
    python custom/scripts/test_dg5f_pub.py [--q 0.3] [--duration 5.0]

When sim_main is running with --enable_dg5f_dds, this should drive DG-5F
finger joints to the commanded angle (visible via livestream viewport
or via rt/dg5f/state subscription showing motor_state[i].q tracking q).
"""

import argparse
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_
from unitree_sdk2py.idl.default import (
    unitree_hg_msg_dds__HandCmd_,
    unitree_hg_msg_dds__MotorCmd_,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--q", type=float, default=0.3, help="target joint angle [rad] for all 20 motors")
    p.add_argument("--kp", type=float, default=80.0)
    p.add_argument("--kd", type=float, default=2.0)
    p.add_argument("--duration", type=float, default=5.0, help="seconds to publish")
    p.add_argument("--rate", type=float, default=20.0, help="publish rate Hz")
    args = p.parse_args()

    ChannelFactoryInitialize(1)
    pub = ChannelPublisher("rt/dg5f/cmd", HandCmd_)
    pub.Init()

    cmd = unitree_hg_msg_dds__HandCmd_()
    # Default factory pre-allocates 7 slots; expand to 20 explicitly.
    cmd.motor_cmd = [unitree_hg_msg_dds__MotorCmd_() for _ in range(20)]
    for i in range(20):
        m = cmd.motor_cmd[i]
        m.mode = 1
        m.q = args.q
        m.dq = 0.0
        m.tau = 0.0
        m.kp = args.kp
        m.kd = args.kd

    n = int(args.duration * args.rate)
    period = 1.0 / args.rate
    print(f"publishing {n} HandCmd_ msgs to rt/dg5f/cmd (q={args.q}, kp={args.kp}, kd={args.kd})...")
    for i in range(n):
        pub.Write(cmd)
        time.sleep(period)
    print("done")


if __name__ == "__main__":
    main()
