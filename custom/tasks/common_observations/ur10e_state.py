"""UR10e arm joint state observation writer.

Same throttled-publisher pattern as DG-5F obs writer; pushes the 6-DoF arm
state into the SHM `isaac_robot_state` consumed by the reused G1RobotDDS
publisher (registered under the name "ur10e" by dds/dds_create.py).

UR10e has no IMU sensor → we send 13 zeros so G1RobotDDS LowState_ population
stays well-defined.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
import torch

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


UR10E_ARM_JOINT_NAMES = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]
ZERO_IMU = [0.0] * 13   # ax,ay,az,wx,wy,wz,qx,qy,qz,qw,acx,acy,acz (G1 layout placeholder)

_obs_cache = {
    "device": None,
    "batch": None,
    "arm_idx_t": None,
    "arm_idx_batch": None,
    "pos_buf": None,
    "vel_buf": None,
    "torque_buf": None,
    "dds_last_ms": 0,
    "dds_min_interval_ms": 10,  # 100 Hz throttle (rt/lowstate target rate)
}

_robot_dds = None
_dds_initialized = False


def _get_robot_dds_instance():
    global _robot_dds, _dds_initialized
    if _dds_initialized and _robot_dds is not None:
        return _robot_dds
    try:
        from dds.dds_master import dds_manager
        _robot_dds = dds_manager.get_object("ur10e")
        if _robot_dds is not None:
            print("[ur10e_state] DDS instance acquired (key='ur10e')")
    except Exception as e:
        print(f"[ur10e_state] failed to get DDS instance: {e}")
        _robot_dds = None
    _dds_initialized = True
    return _robot_dds


def _ensure_indices(env, device):
    if _obs_cache["arm_idx_t"] is not None and _obs_cache["device"] == device:
        return
    joint_names = list(env.scene["robot"].data.joint_names)
    try:
        indices = [joint_names.index(n) for n in UR10E_ARM_JOINT_NAMES]
    except ValueError as e:
        raise RuntimeError(
            f"[ur10e_state] articulation missing UR10e arm joint: {e}; "
            f"available: {joint_names}"
        ) from e
    _obs_cache["arm_idx_t"] = torch.tensor(indices, dtype=torch.long, device=device)
    _obs_cache["device"] = device
    _obs_cache["batch"] = None


def get_ur10e_arm_joint_states(
    env: ManagerBasedRLEnv,
    enable_dds: bool = True,
) -> torch.Tensor:
    """Gather UR10e arm joint pos/vel/torque, throttle-write to G1RobotDDS SHM."""
    joint_pos = env.scene["robot"].data.joint_pos
    joint_vel = env.scene["robot"].data.joint_vel
    joint_torque = env.scene["robot"].data.applied_torque
    device = joint_pos.device
    batch = joint_pos.shape[0]

    _ensure_indices(env, device)
    idx_t = _obs_cache["arm_idx_t"]
    n = idx_t.numel()

    if _obs_cache["batch"] != batch or _obs_cache["arm_idx_batch"] is None:
        _obs_cache["arm_idx_batch"] = idx_t.unsqueeze(0).expand(batch, n)
        _obs_cache["pos_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["vel_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["torque_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["batch"] = batch

    idx_batch = _obs_cache["arm_idx_batch"]
    pos_buf = _obs_cache["pos_buf"]
    vel_buf = _obs_cache["vel_buf"]
    torque_buf = _obs_cache["torque_buf"]

    try:
        torch.gather(joint_pos, 1, idx_batch, out=pos_buf)
        torch.gather(joint_vel, 1, idx_batch, out=vel_buf)
        torch.gather(joint_torque, 1, idx_batch, out=torque_buf)
    except TypeError:
        pos_buf.copy_(torch.gather(joint_pos, 1, idx_batch))
        vel_buf.copy_(torch.gather(joint_vel, 1, idx_batch))
        torque_buf.copy_(torch.gather(joint_torque, 1, idx_batch))

    if enable_dds and pos_buf.shape[0] > 0:
        now_ms = int(time.time() * 1000)
        if now_ms - _obs_cache["dds_last_ms"] >= _obs_cache["dds_min_interval_ms"]:
            robot_dds = _get_robot_dds_instance()
            if robot_dds is not None:
                try:
                    robot_dds.write_robot_state(
                        pos_buf[0].contiguous().cpu().numpy().astype(np.float32),
                        vel_buf[0].contiguous().cpu().numpy().astype(np.float32),
                        torque_buf[0].contiguous().cpu().numpy().astype(np.float32),
                        ZERO_IMU,
                    )
                    _obs_cache["dds_last_ms"] = now_ms
                except Exception as e:
                    print(f"[ur10e_state] DDS write failed: {e}")

    return pos_buf
