"""
UR10e + DG-5F robot preset.

`tasks/common_config/robot_configs.py:RobotBaseCfg.get_base_config()` is humanoid-only
(force-calls `RobotJointTemplates.get_leg_joints()` etc.), so we bypass it and just
return UR10E_WITH_DG5F_HAND with overridden prim_path / init pose.
"""

from typing import Tuple

from isaaclab.assets.articulation import ArticulationCfg
from isaaclab.utils import configclass

from custom.robots.ur10e import UR10E_WITH_DG5F_HAND


@configclass
class UR10ERobotPresets:
    """UR10e + DG-5F robot preset collection."""

    @classmethod
    def ur10e_dg5f(
        cls,
        prim_path: str = "/World/envs/env_.*/Robot",
        init_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        init_rot: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0),
    ) -> ArticulationCfg:
        """UR10e on a fixed base with DG-5F integrated at tool0 (single articulation)."""
        return UR10E_WITH_DG5F_HAND.replace(
            prim_path=prim_path,
            init_state=UR10E_WITH_DG5F_HAND.init_state.replace(
                pos=init_pos,
                rot=init_rot,
            ),
        )
