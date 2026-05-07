"""Isaac-Reach-UR10e-DG5F-Joint task registration."""

import gymnasium as gym

from . import reach_ur10e_dg5f_env_cfg

gym.register(
    id="Isaac-Reach-UR10e-DG5F-Joint",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    kwargs={
        "env_cfg_entry_point": reach_ur10e_dg5f_env_cfg.ReachUR10eDG5FEnvCfg,
    },
    disable_env_checker=True,
)
