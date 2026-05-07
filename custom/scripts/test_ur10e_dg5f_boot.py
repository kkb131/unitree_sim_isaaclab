"""
Standalone Day 2 boot test for the UR10e + DG-5F Reach task.

Bypasses sim_main.py / DDS / action_provider — those are Day 3 work. This script
just creates the env, prints the articulation enumeration (body_names, joint_names),
and runs a few zero-action steps to confirm there's no crash.

Run from the repo root, after `source custom/scripts/activate_env.sh`:

    python custom/scripts/test_ur10e_dg5f_boot.py --headless
    # or with viewport:
    python custom/scripts/test_ur10e_dg5f_boot.py --livestream 2 --public_ip 127.0.0.1
"""

import argparse
import os
import sys

# Ensure the repo root is importable so `import custom...` works regardless of cwd.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="Isaac-Reach-UR10e-DG5F-Joint")
parser.add_argument("--num_steps", type=int, default=50)
parser.add_argument("--num_envs", type=int, default=1)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

# --- Imports below this line require the simulation app to be launched first ---
import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import custom.tasks.ur10e_tasks.reach_ur10e_dg5f  # noqa: F401, E402  — registers gym task
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg  # noqa: E402


def main() -> None:
    env_cfg = parse_env_cfg(args.task, num_envs=args.num_envs)
    env = gym.make(args.task, cfg=env_cfg).unwrapped

    robot = env.scene["robot"]

    print("\n=== Articulation enumeration ===")
    body_names = list(robot.data.body_names)
    joint_names = list(robot.data.joint_names)
    print(f"body_names ({len(body_names)}):")
    for n in body_names:
        print(f"  {n}")
    print(f"joint_names ({len(joint_names)}):")
    for n in joint_names:
        print(f"  {n}")

    n_arm = sum(
        1 for n in joint_names
        if any(k in n for k in ("shoulder", "elbow", "wrist"))
    )
    n_dg5f = sum(1 for n in joint_names if n.startswith("rj_dg_"))
    print(f"\narm joints: {n_arm}, dg5f joints: {n_dg5f}, total: {len(joint_names)}")

    assert len(joint_names) == 26, f"expected 26 joints, got {len(joint_names)}"
    assert n_arm == 6, f"expected 6 UR10e arm joints, got {n_arm}"
    assert n_dg5f == 20, f"expected 20 DG-5F joints, got {n_dg5f}"

    # Check the EE body the env_cfg targets actually exists in the USD.
    from custom.tasks.ur10e_tasks.reach_ur10e_dg5f.reach_ur10e_dg5f_env_cfg import (
        DEFAULT_EE_BODY,
    )
    ee_present = DEFAULT_EE_BODY in body_names
    print(f"\nDEFAULT_EE_BODY '{DEFAULT_EE_BODY}' in body_names: {ee_present}")
    if not ee_present:
        print("  candidates (substring match):")
        for n in body_names:
            if any(k in n for k in ("wrist_3", "tool", "flange", "rl_dg")):
                print(f"    {n}")
        print(
            "  → update DEFAULT_EE_BODY in reach_ur10e_dg5f_env_cfg.py before running training."
        )

    # Run zero-action steps to make sure stepping doesn't crash.
    obs, _ = env.reset()
    action_shape = env.action_manager.action.shape
    device = env.device
    print(f"\nstepping {args.num_steps} zero-action steps (action shape {action_shape})...")
    for _ in range(args.num_steps):
        action = torch.zeros(action_shape, device=device)
        env.step(action)
    print(f"PASS — {args.num_steps} steps executed without crash")

    env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
