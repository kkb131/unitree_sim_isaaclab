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
                "shoulder_pan_joint": 300.0,
                "shoulder_lift_joint": 300.0,
                "elbow_joint": 250.0,
                "wrist_1_joint": 150.0,
                "wrist_2_joint": 150.0,
                "wrist_3_joint": 150.0,
            },
            damping={".*": 8.0},
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
