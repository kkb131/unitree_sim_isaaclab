# Day 2 Spike — UR10e+DG-5F cfg + Reach task boot

> Plan: [/root/.claude/plans/keen-zooming-mist.md](/root/.claude/plans/keen-zooming-mist.md) Day 2 섹션
> Branch: `feat/ur10e-dg5f-sim`
> Day 1 결과: [sim_day1_spike.md](sim_day1_spike.md)

## 0. Scope

USD load + Reach task boot까지. `sim_main.py` / `dds_create.py` / `action_provider_dds.py` 손대지 않음 — DDS 작업은 Day 3.

## 1. 신규 파일 (모두 `custom/` 하위)

| 파일 | 역할 |
|---|---|
| `custom/__init__.py` (+ 5 sub) | Python module 체인 |
| [`custom/robots/ur10e.py`](../robots/ur10e.py) | `UR10E_WITH_DG5F_HAND` ArticulationCfg |
| [`custom/tasks/common_config/ur10e_configs.py`](../tasks/common_config/ur10e_configs.py) | `UR10ERobotPresets.ur10e_dg5f()` (RobotBaseCfg.get_base_config 우회) |
| [`custom/tasks/ur10e_tasks/__init__.py`](../tasks/ur10e_tasks/__init__.py) | `from . import reach_ur10e_dg5f` (gym.register trigger) |
| [`custom/tasks/ur10e_tasks/reach_ur10e_dg5f/__init__.py`](../tasks/ur10e_tasks/reach_ur10e_dg5f/__init__.py) | `gym.register("Isaac-Reach-UR10e-DG5F-Joint", ...)` |
| [`custom/tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py`](../tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py) | `ReachUR10eDG5FEnvCfg` (Scene/Cmd/Action/Obs/Reward/Term) |
| [`custom/tasks/ur10e_tasks/reach_ur10e_dg5f/mdp/__init__.py`](../tasks/ur10e_tasks/reach_ur10e_dg5f/mdp/__init__.py) | re-export `isaaclab.envs.mdp` + `isaaclab_tasks.manager_based.manipulation.reach.mdp` |
| [`custom/scripts/test_ur10e_dg5f_boot.py`](../scripts/test_ur10e_dg5f_boot.py) | Standalone boot test (sim_main 우회) |

upstream 파일 수정: **0건**.

## 2. 주요 설계 결정

### 2.1 `RobotBaseCfg.get_base_config()` 우회

[robot_configs.py:170-239](/workspace/isaaclab/datasets/unitree_sim_isaaclab/tasks/common_config/robot_configs.py#L170-L239) 의 `get_base_config()`는 `RobotJointTemplates.get_leg_joints()` / `get_waist_joints()` / `get_arm_joints()` 를 강제 호출 — humanoid 전용. UR10e는 leg/waist 없으므로 우회. `UR10ERobotPresets.ur10e_dg5f()` 는 `UR10E_WITH_DG5F_HAND.replace(prim_path, init_state)` 직접 반환.

### 2.2 PD gains (Day 5 보정 예정)

UR10e arm (industrial, H1-2 humanoid보다 stiffer):
- shoulder_pan/lift: kp=300
- elbow: kp=250
- wrist 1/2/3: kp=150
- 모두 kd=8

DG-5F (Inspire H12 cfg 동일값):
- 모든 finger joint: kp=1000, kd=15
- effort_limit=100, velocity_limit=50, armature=0

### 2.3 `--merge-joints` 영향 후동 확정

Day 1 caveat이었던 link 흡수가 실제 어떻게 됐는지 확인됨 — body_names 27개:

```
world, shoulder_link, upper_arm_link, forearm_link,
wrist_1_link, wrist_2_link, wrist_3_link,           ← UR10e 7 link
rl_dg_{1..5}_1,                                      ← finger 첫째 마디 5개
rl_dg_{1..5}_2,
rl_dg_{1..5}_3,
rl_dg_{1..5}_4                                       ← finger 마지막 마디 5개
```

**`tool0`/`flange`/`ft_frame`/`base`/`base_link`/`base_link_inertia` 모두 `wrist_3_link` 또는 `world`로 흡수**. `rl_dg_mount`/`rl_dg_base`/`rl_dg_palm` 도 `wrist_3_link`로 흡수. `rl_dg_{1..5}_tip` 도 각 finger 마지막 마디로 흡수.

**중요한 결과**: `wrist_3_link`이 살아있어 EE body 참조 그대로 OK. CommandsCfg/RewardsCfg `body_name="wrist_3_link"` 보정 불필요.

### 2.4 Joint 등장 순서 (Day 3 DDS motor index 참조용)

`robot.data.joint_names` 출력 순서:
```
[ 0] shoulder_pan_joint
[ 1] shoulder_lift_joint
[ 2] elbow_joint
[ 3] wrist_1_joint
[ 4] wrist_2_joint
[ 5] wrist_3_joint
[ 6] rj_dg_1_1     ← finger 1 첫 마디
[ 7] rj_dg_2_1
[ 8] rj_dg_3_1
[ 9] rj_dg_4_1
[10] rj_dg_5_1
[11] rj_dg_1_2     ← finger 1 둘째 마디
... (5 fingers × 4 마디 round-robin)
[25] rj_dg_5_4     ← finger 5 마지막 마디
```

DDS `rt/lowcmd.motor_cmd[0:6]` → joint[0:6] (UR10e arm) 매핑은 자명.
DDS `rt/dg5f/cmd.motor_cmd[0:20]` → joint[6:26] (DG-5F) 매핑은 위 round-robin 순서. Day 3 dg5f_provider.py 작성 시 이 순서대로 인덱싱.

## 3. 부팅 검증 결과

```
$ python custom/scripts/test_ur10e_dg5f_boot.py --headless
=== Articulation enumeration ===
body_names (27): [위 §2.3 list]
joint_names (26): [위 §2.4 list]
arm joints: 6, dg5f joints: 20, total: 26

DEFAULT_EE_BODY 'wrist_3_link' in body_names: True

stepping 50 zero-action steps (action shape torch.Size([1, 26]))...
PASS — 50 steps executed without crash
```

✅ Day 2 통과 기준 5/5 모두 충족 (livestream 시각 확인은 미수행 — headless로 충분).

## 4. 시행착오 (다른 PC에서 재현 시 참고)

1. **`ModuleNotFoundError: No module named 'custom'`** — script가 `import custom.tasks...` 할 때 PYTHONPATH에 repo root 없으면 실패. `test_ur10e_dg5f_boot.py` 가 `__file__` 기반으로 sys.path 부트스트랩 (line 14-17 부근).
2. **`AttributeError: module 'mdp' has no attribute 'position_command_error'`** — `isaaclab.envs.mdp` 에는 reach-specific reward 없음. `isaaclab_tasks.manager_based.manipulation.reach.mdp` 도 `mdp/__init__.py` 에서 함께 re-export.
3. **stdout buffering으로 print 출력 누락** — `python -u` (unbuffered) 또는 `print(..., flush=True)` 필요. boot test 스크립트는 -u 권장.
4. **`enable_external_forces_every_iteration` warning** — IsaacLab 0.46.6 PhysxCfg 기본값 관련. 동작에 영향 없음, 무시.
5. **`'effort_limit'/'velocity_limit' deprecation warning`** — IsaacLab 미래 버전에서 `effort_limit_sim`/`velocity_limit_sim` 으로 변경 예고. Day 2 단계에선 그대로 유지.

## 5. Day 3 진입 가능 여부

✅ 진입 가능. Day 3 작업 내용:
1. `dds/dg5f_dds.py` 신규 (HandCmd_/HandState_ + 20 motor)
2. `tasks/common_observations/dg5f_state.py` 신규 (joint state → SHM writer)
3. `dds/dds_create.py` 수정 — `--enable_dg5f_dds` 분기 + `robot_type=ur10e` 분기
4. `action_provider/action_provider_dds.py` 수정 — UR10e arm + DG-5F joint mapping
5. `sim_main.py` 수정 — `--enable_dg5f_dds` argparse + 4-way mutual exclusion
6. 검증: rt/lowstate publish (motor[0:6]) + rt/dg5f/state publish (motor_state[0:20])
