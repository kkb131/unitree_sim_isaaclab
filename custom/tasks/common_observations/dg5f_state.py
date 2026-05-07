"""DG-5F joint state observation writer.

Pattern mirrored from `tasks/common_observations/inspire_state.py`. Each env
step (throttled to 50 Hz) we gather 20 finger joint pos/vel/torque from the
articulation and push them into the SHM the DG5FDDS publisher reads.

Joint order (matches finger-major DDS convention used by action_provider):
  DDS 0..3   = rj_dg_1_{1..4}   (finger 1)
  DDS 4..7   = rj_dg_2_{1..4}   (finger 2)
  DDS 8..11  = rj_dg_3_{1..4}   (finger 3)
  DDS 12..15 = rj_dg_4_{1..4}   (finger 4)
  DDS 16..19 = rj_dg_5_{1..4}   (finger 5)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


DG5F_JOINT_NAMES = [f"rj_dg_{f}_{j}" for f in (1, 2, 3, 4, 5) for j in (1, 2, 3, 4)]

_obs_cache = {
    "device": None,
    "batch": None,
    "dg5f_idx_t": None,
    "dg5f_idx_batch": None,
    "pos_buf": None,
    "vel_buf": None,
    "torque_buf": None,
    "dds_last_ms": 0,
    "dds_min_interval_ms": 20,  # 50 Hz throttle
}

_dg5f_dds = None
_dds_initialized = False


def _get_dg5f_dds_instance():
    global _dg5f_dds, _dds_initialized
    if _dds_initialized and _dg5f_dds is not None:
        return _dg5f_dds
    try:
        from dds.dds_master import dds_manager
        _dg5f_dds = dds_manager.get_object("dg5f")
        if _dg5f_dds is not None:
            print("[dg5f_state] DDS instance acquired")
    except Exception as e:
        print(f"[dg5f_state] failed to get DDS instance: {e}")
        _dg5f_dds = None
    _dds_initialized = True
    return _dg5f_dds


def _ensure_indices(env, device):
    if _obs_cache["dg5f_idx_t"] is not None and _obs_cache["device"] == device:
        return
    joint_names = list(env.scene["robot"].data.joint_names)
    try:
        indices = [joint_names.index(n) for n in DG5F_JOINT_NAMES]
    except ValueError as e:
        raise RuntimeError(
            f"[dg5f_state] articulation missing expected DG-5F joint: {e}; "
            f"available: {joint_names}"
        ) from e
    _obs_cache["dg5f_idx_t"] = torch.tensor(indices, dtype=torch.long, device=device)
    _obs_cache["device"] = device
    _obs_cache["batch"] = None


def get_robot_dg5f_joint_states(
    env: ManagerBasedRLEnv,
    enable_dds: bool = True,
) -> torch.Tensor:
    """Gather DG-5F joint pos/vel/torque, throttle-write to DG5FDDS SHM, return pos."""
    joint_pos = env.scene["robot"].data.joint_pos
    joint_vel = env.scene["robot"].data.joint_vel
    joint_torque = env.scene["robot"].data.applied_torque
    device = joint_pos.device
    batch = joint_pos.shape[0]

    _ensure_indices(env, device)
    idx_t = _obs_cache["dg5f_idx_t"]
    n = idx_t.numel()

    if _obs_cache["batch"] != batch or _obs_cache["dg5f_idx_batch"] is None:
        _obs_cache["dg5f_idx_batch"] = idx_t.unsqueeze(0).expand(batch, n)
        _obs_cache["pos_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["vel_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["torque_buf"] = torch.empty(batch, n, device=device, dtype=joint_pos.dtype)
        _obs_cache["batch"] = batch

    idx_batch = _obs_cache["dg5f_idx_batch"]
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
            dg5f_dds = _get_dg5f_dds_instance()
            if dg5f_dds is not None:
                try:
                    dg5f_dds.write_dg5f_state(
                        pos_buf[0].contiguous().cpu().numpy(),
                        vel_buf[0].contiguous().cpu().numpy(),
                        torque_buf[0].contiguous().cpu().numpy(),
                    )
                    _obs_cache["dds_last_ms"] = now_ms
                except Exception as e:
                    print(f"[dg5f_state] DDS write failed: {e}")

    return pos_buf
