"""
ArticulationCfg for UR10e (6-DoF arm) + Tesollo DG-5F (5-finger, 20 revolute) hand.

Pattern adapted from `robots/unitree.py:H12_CFG_WITH_INSPIRE_HAND`. The USD is
the integrated `assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd` produced by
`custom/tools/build_ur10e_dg5f_assets.sh` (Day 1).
"""

import os

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg

# Resolve repo root: PROJECT_ROOT env var (set by activate_env.sh in some setups),
# else compute from this file's location (custom/robots/ur10e.py → ../..).
REPO_ROOT = os.environ.get("PROJECT_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

UR10E_USD_PATH = f"{REPO_ROOT}/assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd"


UR10E_WITH_DG5F_HAND = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=UR10E_USD_PATH,
        activate_contact_sensors=True,
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            retain_accelerations=True,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=False,
            solver_position_iteration_count=8,
            solver_velocity_iteration_count=4,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.0),
        rot=(1.0, 0.0, 0.0, 0.0),
        joint_pos={
            # UR10e arm — "ready" pose: tool0 points forward with elbow up
            "shoulder_pan_joint": 0.0,
            "shoulder_lift_joint": -1.57,
            "elbow_joint": 1.57,
            "wrist_1_joint": -1.57,
            "wrist_2_joint": -1.57,
            "wrist_3_joint": 0.0,
            # DG-5F open hand — all 20 finger joints at zero
            "rj_dg_.*": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    soft_joint_pos_limit_factor=0.9,
    actuators={
        # Day 5 PD tune — initial values (kp=300/kd=8) left shoulder_lift with
        # a 0.4 rad steady-state error at target=-1.0 (gravity-loaded). UR10e
        # is a ~33 kg arm; literature PD gains for similar 6-DoF industrial
        # arms sit in the 1000-3000 N·m/rad range for shoulder/elbow.
        # Damping bumped roughly in proportion so settling stays critically
        # damped (no visible oscillation under DDS step commands).
        "arm": ImplicitActuatorCfg(
            joint_names_expr=[
                "shoulder_pan_joint",
                "shoulder_lift_joint",
                "elbow_joint",
                "wrist_1_joint",
                "wrist_2_joint",
                "wrist_3_joint",
            ],
            effort_limit=None,
            velocity_limit=None,
            stiffness={
                "shoulder_pan_joint": 1000.0,
                "shoulder_lift_joint": 2500.0,
                "elbow_joint": 1500.0,
                "wrist_1_joint": 500.0,
                "wrist_2_joint": 300.0,
                "wrist_3_joint": 200.0,
            },
            damping={
                "shoulder_pan_joint": 50.0,
                "shoulder_lift_joint": 80.0,
                "elbow_joint": 60.0,
                "wrist_1_joint": 25.0,
                "wrist_2_joint": 20.0,
                "wrist_3_joint": 15.0,
            },
            armature=None,
        ),
        "dg5f": ImplicitActuatorCfg(
            joint_names_expr=["rj_dg_.*"],
            effort_limit=100.0,
            velocity_limit=50.0,
            stiffness={"rj_dg_.*": 1000.0},
            damping={"rj_dg_.*": 15.0},
            armature={".*": 0.0},
        ),
    },
)
