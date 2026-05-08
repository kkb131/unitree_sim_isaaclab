"""
Manager-based RL environment cfg for the UR10e + DG-5F Reach task.

Day 2 scope: USD load + boot. The environment is structured in the standard
IsaacLab reach style (UniformPoseCommandCfg + position/orientation command-error
rewards) so it can later be trained with PPO; for Day 2 we just verify it boots
and 26 joints + the chosen EE body are correct.
"""

import math

from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import (
    EventTermCfg as EventTerm,
    ObservationGroupCfg as ObsGroup,
    ObservationTermCfg as ObsTerm,
    RewardTermCfg as RewTerm,
    SceneEntityCfg,
    TerminationTermCfg as DoneTerm,
)
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.assets import AssetBaseCfg
from isaaclab.sim import GroundPlaneCfg, DomeLightCfg
from isaaclab.utils import configclass

from custom.tasks.common_config.ur10e_camera_configs import UR10ECameraPresets
from custom.tasks.common_config.ur10e_configs import UR10ERobotPresets
from tasks.common_observations import camera_state
from custom.tasks.common_observations import dg5f_state, ur10e_state

from . import mdp


# Default end-effector body name. The Day 1 USD was built with
# --merge-joints, which collapses tool0/flange/rl_dg_mount into wrist_3_link;
# Day 2 boot test (custom/scripts/test_ur10e_dg5f_boot.py) prints the actual
# body_names so this can be corrected if needed before training.
DEFAULT_EE_BODY = "wrist_3_link"


@configclass
class UR10eReachSceneCfg(InteractiveSceneCfg):
    """Scene: ground + dome light + UR10e+DG-5F robot + 2 cameras (Day 4)."""

    ground = AssetBaseCfg(
        prim_path="/World/ground",
        spawn=GroundPlaneCfg(),
    )
    dome_light = AssetBaseCfg(
        prim_path="/World/Light",
        spawn=DomeLightCfg(intensity=2000.0, color=(0.9, 0.9, 0.9)),
    )
    robot = UR10ERobotPresets.ur10e_dg5f()

    # Day 4 cameras — scene attribute names MUST be `front_camera` /
    # `right_wrist_camera` exactly (camera_state.py hardcodes them).
    # `left_wrist_camera` intentionally omitted (single-arm UR10e). Boot with
    # --camera_include "front_camera,right_wrist_camera" so the sensor
    # allowlist matches the scene.
    front_camera = UR10ECameraPresets.ur10e_front_camera()
    right_wrist_camera = UR10ECameraPresets.ur10e_right_wrist_camera()


@configclass
class CommandsCfg:
    """End-effector pose target generated uniformly within a workspace box."""

    ee_pose = mdp.UniformPoseCommandCfg(
        asset_name="robot",
        body_name=DEFAULT_EE_BODY,
        resampling_time_range=(4.0, 4.0),
        debug_vis=True,
        ranges=mdp.UniformPoseCommandCfg.Ranges(
            pos_x=(0.3, 0.6),
            pos_y=(-0.3, 0.3),
            pos_z=(0.4, 0.8),
            roll=(0.0, 0.0),
            pitch=(math.pi / 2, math.pi / 2),
            yaw=(-math.pi, math.pi),
        ),
    )


@configclass
class ActionsCfg:
    """Direct joint-position action over all 26 joints (arm + hand).

    `use_default_offset=False` so DDS commands are interpreted as absolute joint
    angles (matches the build guide spec; xr_teleop sends absolute targets).
    """

    arm_action = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=[".*"],
        scale=1.0,
        use_default_offset=False,
    )


@configclass
class ObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        pose_command = ObsTerm(func=mdp.generated_commands, params={"command_name": "ee_pose"})
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    @configclass
    class DDSStateGroup(ObsGroup):
        """Side-effect terms that publish joint state to DDS each step.

        `concatenate_terms=False` so these don't pollute the policy obs vector;
        the observation manager still calls them every step.
        """

        ur10e_arm = ObsTerm(func=ur10e_state.get_ur10e_arm_joint_states)
        dg5f_hand = ObsTerm(func=dg5f_state.get_robot_dg5f_joint_states)
        # Day 4 — drives the teleimager pipeline (env.scene[front/right_wrist_camera]
        # → SHM → ZMQ 55555/55557 + WebRTC 60001/60003).
        camera_image = ObsTerm(func=camera_state.get_camera_image)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = False

    policy: PolicyCfg = PolicyCfg()
    dds: DDSStateGroup = DDSStateGroup()


@configclass
class RewardsCfg:
    end_effector_position_tracking = RewTerm(
        func=mdp.position_command_error,
        weight=-0.2,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=[DEFAULT_EE_BODY]),
            "command_name": "ee_pose",
        },
    )
    end_effector_position_tracking_fine_grained = RewTerm(
        func=mdp.position_command_error_tanh,
        weight=0.1,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=[DEFAULT_EE_BODY]),
            "command_name": "ee_pose",
            "std": 0.1,
        },
    )
    end_effector_orientation_tracking = RewTerm(
        func=mdp.orientation_command_error,
        weight=-0.1,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=[DEFAULT_EE_BODY]),
            "command_name": "ee_pose",
        },
    )
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-1e-4)
    joint_vel = RewTerm(
        func=mdp.joint_vel_l2,
        weight=-1e-4,
        params={"asset_cfg": SceneEntityCfg("robot")},
    )


@configclass
class TerminationsCfg:
    time_out = DoneTerm(func=mdp.time_out, time_out=True)


@configclass
class EventCfg:
    """No randomization for Day 2 boot — keep deterministic."""

    pass


@configclass
class ReachUR10eDG5FEnvCfg(ManagerBasedRLEnvCfg):
    scene: UR10eReachSceneCfg = UR10eReachSceneCfg(num_envs=1, env_spacing=2.5)
    commands: CommandsCfg = CommandsCfg()
    actions: ActionsCfg = ActionsCfg()
    observations: ObservationsCfg = ObservationsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()

    def __post_init__(self):
        self.decimation = 2
        self.episode_length_s = 10.0
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
