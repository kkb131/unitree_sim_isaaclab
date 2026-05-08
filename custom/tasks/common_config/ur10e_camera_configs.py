"""
UR10e + DG-5F camera presets.

Two cameras for the single-arm UR10e setup:
- `front_camera`: fixed third-person view, mounted on world body to frame the
   workspace. Pos/rot offsets tuned at first boot via livestream viewport.
- `right_wrist_camera`: palm-view egocentric, mounted on `wrist_3_link`
   (--merge-joints absorbed tool0 / flange / rl_dg_mount / rl_dg_palm into it).

`left_wrist_camera` is intentionally NOT defined here — UR10e is single-arm.
Boot the sim with `--camera_include "front_camera,right_wrist_camera"` so the
default sensor allowlist disables the missing camera (avoids needless
update_period=1e6 cycle on a non-existent attribute).

Pattern follows `tasks/common_config/camera_configs.py:CameraPresets`. Scene
attribute names MUST be `front_camera` / `right_wrist_camera` exactly so that
[camera_state.py:113-131](../../../tasks/common_observations/camera_state.py)
maps them to images["head"]/images["right"] for the teleimager publisher.
"""

from isaaclab.sensors import CameraCfg
from isaaclab.utils import configclass

from tasks.common_config.camera_configs import CameraBaseCfg


@configclass
class UR10ECameraPresets:
    """Camera presets for the UR10e + DG-5F task."""

    @classmethod
    def ur10e_front_camera(cls) -> CameraCfg:
        """Fixed third-person camera mounted on world body, framing the workspace."""
        return CameraBaseCfg.get_camera_config(
            prim_path="/World/envs/env_.*/Robot/world/front_cam",
            height=480,
            width=640,
            focal_length=12.0,
            horizontal_aperture=20.0,
            # Place camera 0.8m behind robot base and 0.6m above, looking down ~30°.
            # Offset is in the world body's local frame (which equals world frame
            # for the fixed-base UR10e). Tune at first boot via livestream.
            pos_offset=(-0.8, 0.0, 0.6),
            rot_offset=(0.6533, -0.2706, 0.2706, -0.6533),
        )

    @classmethod
    def ur10e_right_wrist_camera(cls) -> CameraCfg:
        """Palm-view egocentric camera mounted on wrist_3_link (DG-5F palm region)."""
        return CameraBaseCfg.get_camera_config(
            prim_path="/World/envs/env_.*/Robot/wrist_3_link/right_wrist_camera",
            height=480,
            width=640,
            focal_length=12.0,
            horizontal_aperture=20.0,
            # 10cm in front of wrist_3 along its forward axis (palm direction).
            pos_offset=(0.0, 0.0, 0.10),
            rot_offset=(0.5, -0.5, 0.5, -0.5),
        )
