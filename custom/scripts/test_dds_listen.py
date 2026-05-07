"""Subscribe to rt/lowstate and rt/dg5f/state for ~3 seconds and report counts.

Usage:
    source custom/scripts/activate_env.sh
    python custom/scripts/test_dds_listen.py [--duration 3.0]

Expected with sim_main running --robot_type ur10e --enable_dg5f_dds:
    rt/lowstate ~280 msg / 3s   (≈94 Hz)
    rt/dg5f/state ~150 msg / 3s (≈50 Hz, throttled by obs writer)
"""

import argparse
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandState_, LowState_


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration", type=float, default=3.0, help="seconds to listen")
    args = p.parse_args()

    ChannelFactoryInitialize(1)

    counts = {"lowstate": 0, "dg5f_state": 0}
    samples = {"lowstate": None, "dg5f_state": None}

    def cb_low(msg: LowState_) -> None:
        counts["lowstate"] += 1
        if samples["lowstate"] is None and len(msg.motor_state) >= 6:
            samples["lowstate"] = [round(float(msg.motor_state[i].q), 4) for i in range(6)]

    def cb_dg5f(msg: HandState_) -> None:
        counts["dg5f_state"] += 1
        if samples["dg5f_state"] is None and len(msg.motor_state) >= 20:
            samples["dg5f_state"] = [round(float(msg.motor_state[i].q), 4) for i in range(20)]

    sub_low = ChannelSubscriber("rt/lowstate", LowState_)
    sub_low.Init(cb_low, 32)
    sub_dg5f = ChannelSubscriber("rt/dg5f/state", HandState_)
    sub_dg5f.Init(cb_dg5f, 32)

    print(f"listening for {args.duration:.1f}s...")
    time.sleep(args.duration)

    sub_low.Close()
    sub_dg5f.Close()

    rate_low = counts["lowstate"] / args.duration
    rate_dg5f = counts["dg5f_state"] / args.duration
    print(f"\n=== results ({args.duration:.1f}s) ===")
    print(f"rt/lowstate    : {counts['lowstate']:5d} msgs ({rate_low:6.1f} Hz)  motor[0:6].q = {samples['lowstate']}")
    print(f"rt/dg5f/state  : {counts['dg5f_state']:5d} msgs ({rate_dg5f:6.1f} Hz)  motor[0:20].q = {samples['dg5f_state']}")

    pass_low = counts["lowstate"] >= int(args.duration * 50)   # ≥50 Hz
    pass_dg5f = counts["dg5f_state"] >= int(args.duration * 20)  # ≥20 Hz
    print(f"\nlowstate PASS: {pass_low}, dg5f_state PASS: {pass_dg5f}")


if __name__ == "__main__":
    main()
