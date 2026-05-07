"""Publish LowCmd_ targets for the UR10e 6-DoF arm and verify tracking via rt/lowstate.

Usage:
    source custom/scripts/activate_env.sh
    python custom/scripts/test_lowcmd_pub.py [--target 0.3,...] [--duration 5]

When sim_main is running with --robot_type ur10e, the UR10e arm should drive
toward the commanded angles. After publishing, listen briefly to rt/lowstate
to confirm motor[0:6].q tracks the targets.
"""

import argparse
import time

from unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelPublisher,
    ChannelSubscriber,
)
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import (
    unitree_hg_msg_dds__LowCmd_,
    unitree_hg_msg_dds__MotorCmd_,
)
from unitree_sdk2py.utils.crc import CRC


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--target",
        type=str,
        default="0.0,-1.0,1.2,-1.2,-1.5,0.0",
        help="comma-separated 6 target angles for shoulder_pan/lift/elbow/wrist_{1,2,3}",
    )
    p.add_argument("--kp", type=float, default=200.0)
    p.add_argument("--kd", type=float, default=10.0)
    p.add_argument("--duration", type=float, default=5.0, help="seconds to publish")
    p.add_argument("--rate", type=float, default=20.0)
    args = p.parse_args()

    targets = [float(x) for x in args.target.split(",")]
    if len(targets) != 6:
        raise SystemExit("--target must have exactly 6 comma-separated values")

    ChannelFactoryInitialize(1)
    crc = CRC()

    pub = ChannelPublisher("rt/lowcmd", LowCmd_)
    pub.Init()

    cmd = unitree_hg_msg_dds__LowCmd_()
    # Default factory pre-allocates 35 motor_cmd slots — enough for our 6.
    for i, q in enumerate(targets):
        m = cmd.motor_cmd[i]
        m.mode = 1
        m.q = q
        m.dq = 0.0
        m.tau = 0.0
        m.kp = args.kp
        m.kd = args.kd

    n = int(args.duration * args.rate)
    period = 1.0 / args.rate
    print(f"publishing {n} LowCmd_ msgs to rt/lowcmd, targets={targets}")
    for _ in range(n):
        cmd.crc = crc.Crc(cmd)
        pub.Write(cmd)
        time.sleep(period)
    print("publish done — verifying rt/lowstate tracking...")

    last_state = {"q": None}

    def cb(msg: LowState_) -> None:
        if len(msg.motor_state) >= 6:
            last_state["q"] = [round(float(msg.motor_state[i].q), 3) for i in range(6)]

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(cb, 32)
    time.sleep(1.0)
    sub.Close()

    if last_state["q"] is None:
        print("FAIL — no rt/lowstate received")
        return

    err = [abs(t - q) for t, q in zip(targets, last_state["q"])]
    print(f"  targets : {targets}")
    print(f"  measured: {last_state['q']}")
    print(f"  abs err : {[round(e, 3) for e in err]}")
    pass_track = all(e < 0.05 for e in err)
    print(f"\nUR10e arm tracking PASS (all err < 0.05 rad): {pass_track}")


if __name__ == "__main__":
    main()
