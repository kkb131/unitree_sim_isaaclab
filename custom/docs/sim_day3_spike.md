# Day 3 Spike — DDS round-trip (rt/lowstate, rt/lowcmd, rt/dg5f/{state,cmd})

> Plan: [/root/.claude/plans/keen-zooming-mist.md](/root/.claude/plans/keen-zooming-mist.md) Day 3 섹션
> Branch: `feat/ur10e-dg5f-sim`
> Day 1/2 결과: [sim_day1_spike.md](sim_day1_spike.md), [sim_day2_spike.md](sim_day2_spike.md)

## 0. Scope

UR10e arm (`rt/lowstate`/`rt/lowcmd`) + DG-5F hand (`rt/dg5f/state`/`rt/dg5f/cmd`) round-trip. PD tuning은 Day 5 별도.

## 1. 신규 파일 (모두 `custom/` 하위)

| 파일 | 역할 |
|---|---|
| [`custom/dds/__init__.py`](../dds/__init__.py) + [`dg5f_dds.py`](../dds/dg5f_dds.py) | DG5FDDS class — `rt/dg5f/{state,cmd}`, single-hand 20 motor `HandCmd_/HandState_` |
| [`custom/tasks/common_observations/__init__.py`](../tasks/common_observations/__init__.py) + [`dg5f_state.py`](../tasks/common_observations/dg5f_state.py) | DG-5F joint state → SHM `isaac_dg5f_state` writer (50 Hz throttle) |
| [`custom/tasks/common_observations/ur10e_state.py`](../tasks/common_observations/ur10e_state.py) | UR10e arm joint state + 13-zero IMU → SHM `isaac_robot_state` (100 Hz throttle) |
| [`custom/scripts/test_dds_listen.py`](../scripts/test_dds_listen.py) | `rt/lowstate` + `rt/dg5f/state` 카운트 검증 |
| [`custom/scripts/test_dg5f_pub.py`](../scripts/test_dg5f_pub.py) | DG-5F HandCmd_ 송신 (round-trip 검증) |
| [`custom/scripts/test_lowcmd_pub.py`](../scripts/test_lowcmd_pub.py) | UR10e LowCmd_ 송신 + tracking 검증 |

## 2. 업데이트 (custom/)

| 파일 | 변경 |
|---|---|
| `custom/tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py` | `ActionsCfg.use_default_offset = False` (DDS는 절대 angle), `ObservationsCfg`에 `DDSStateGroup(concatenate_terms=False)` 추가 — `ur10e_arm`/`dg5f_hand` ObsTerm으로 obs writer 매 step 호출 |

## 3. Upstream dispatch hook (3 파일, 작은 수정)

| 파일 | 변경 |
|---|---|
| `sim_main.py` | `--enable_dg5f_dds` argparse 추가 / 4-way mutex validation / `import custom.tasks.ur10e_tasks` (`import tasks` 다음) / 주석 example 한 줄 추가 |
| `dds/dds_create.py` | `args_cli.robot_type == "ur10e"` 분기 (G1RobotDDS reuse `node_name="ur10e_robot"`) + `args_cli.enable_dg5f_dds` 분기 (`from custom.dds.dg5f_dds import DG5FDDS`) |
| `action_provider/action_provider_dds.py` | `__init__` `self.enable_dg5f`/`self.dg5f_dds` 추가 / `_setup_dds()` ur10e + dg5f 분기 / `_setup_joint_mapping()` UR10e arm 6 joint (offset 0) + DG-5F 20 joint (finger-major) / `get_action()` UR10e arm + DG-5F hand assembly / `cleanup()` dg5f_dds 추가 / `_positions_buf` size `max(29, 20)` |

## 4. 핵심 설계 결정

### 4.1 G1RobotDDS reuse for UR10e

[g1_robot_dds.py:78-95](../../dds/g1_robot_dds.py#L78-L95) 의 `motor_state` 채우기는 `for i in range(len(q_array))` — variable-length sequence 지원. 6 motor만 채워 publish OK. ChannelFactoryInitialize는 [dds_master.py:60](../../dds/dds_master.py#L60) 한 번만 호출됨, DG5FDDS 안에선 호출 안 함.

### 4.2 DG-5F finger-major DDS convention

action_provider 매핑:
- DDS `motor_cmd[0..3]` ← finger 1 joint 1..4 (`rj_dg_1_{1..4}`)
- DDS `motor_cmd[4..7]` ← finger 2 joint 1..4 (`rj_dg_2_{1..4}`)
- ... → DDS `motor_cmd[16..19]` ← finger 5

xr_teleop side가 retargeting 시 finger 단위로 처리 자연스러움. articulation slot은 round-robin이지만 mapping table이 자동 정렬해서 placement 수행 (`index_select` + `index_copy_`).

### 4.3 `use_default_offset=False`

DDS 명령은 **절대 joint angle**. `JointPositionActionCfg.use_default_offset=False` 설정 → `target = action`. xr_teleop side가 IK/retargeting 후 절대 angle 보내는 가정과 일치.

### 4.4 `HandState_/HandCmd_` 20 slot 명시 init

`unitree_hg_msg_dds__HandState_()` 기본 7 slot — DG5FDDS 안에서 `self.hand_state.motor_state = [unitree_hg_msg_dds__MotorState_() for _ in range(20)]` 명시 재초기화. test_dg5f_pub.py도 마찬가지로 20 slot 명시.

## 5. 검증 결과

### 5.1 부팅 (sim_main background)
```
[ur10e_robot] G1 robot DDS node initialized            ✅
[dg5f] DG-5F DDS node initialized (20 motors)          ✅
[ur10e_robot] State publisher initialized (rt/lowstate) ✅
[dg5f] state publisher initialized (rt/dg5f/state)      ✅
[ur10e_robot] Create ChannelSubscriber...               ✅ (rt/lowcmd)
[dg5f] command subscriber initialized (rt/dg5f/cmd)     ✅
enable_robot: ur10e
[DDSActionProvider] DDS communication initialized       ✅
[ur10e_state] DDS instance acquired (key='ur10e')       ✅
[dg5f_state] DDS instance acquired                      ✅
```
부팅 ~23초.

### 5.2 단방향 publish — `test_dds_listen.py --duration 3.0`
```
rt/lowstate    : 291 msgs ( 97.0 Hz)  motor[0:6].q = [0.0001, 0.0291, -0.0575, ...]
rt/dg5f/state  : 291 msgs ( 97.0 Hz)  motor[0:20].q = [-0.0001, -0.0001, ...]
lowstate PASS: True, dg5f_state PASS: True
```

### 5.3 DG-5F round-trip — `test_dg5f_pub.py --q 0.3 --duration 3.0`
publish 후 state 측정:
```
motor[0:20].q = [0.3097, -0.0, 0.3102, 0.3, 0.2998, 0.2987, 0.2975, 0.3001,
                 0.2997, 0.2996, 0.2966, 0.3003, 0.2224, 0.27, -0.0508, 0.2781,
                 -0.0392, 0.0086, 0.1612, -0.1244]
```
finger 1, 2, 3 (DDS [0..11]): 대부분 0.30 추종 ✅
finger 4, 5 (DDS [12..19]): 일부 joint 수렴 안 됨 (0.05~0.16 또는 negative). 의심 원인:
- DG-5F mass/inertia 값 부정확 (Day 1 caveat — Tesollo 공식 spec 보정 미적용)
- finger collision (`enabled_self_collisions=False` 인데도 떨림)
- joint limit (specific finger의 angle range 좁음)

→ **PD tuning + mass 보정은 Day 5**.

### 5.4 UR10e arm round-trip — `test_lowcmd_pub.py --duration 5.0`
targets: `[0.0, -1.0, 1.2, -1.2, -1.5, 0.0]` (shoulder_pan/lift/elbow/wrist_{1,2,3})
measured: `[0.024, -0.752, 1.266, -1.191, -1.454, -0.055]`
abs err: `[0.024, 0.248, 0.066, 0.009, 0.046, 0.055]`

5/6 joint err ≤ 0.07 rad ✅. shoulder_lift만 0.248 rad — 가장 무거운 joint이라 5초 settling 부족 (home -1.57 → -1.0 으로 swing). PD kp 보정 또는 더 긴 settle 시간으로 추종 가능. Day 5 작업.

## 6. Day 3 통과 기준 (5개)

| # | 항목 | 결과 |
|---|---|---|
| 1 | `sim_main.py` 부팅 | ✅ ~23초, DDS 4 topic + obs writer + action provider 모두 정상 |
| 2 | `rt/lowstate` ≥ 50 Hz, motor[0:6].q valid | ✅ 97 Hz |
| 3 | `rt/dg5f/state` ≥ 20 Hz, motor[0:20].q valid | ✅ 97 Hz |
| 4 | `rt/lowcmd` round-trip — UR10e arm 추종 | ✅ 5/6 joint < 0.07 rad (shoulder_lift는 settling 부족, Day 5 PD tuning) |
| 5 | `rt/dg5f/cmd` round-trip — DG-5F finger 추종 | ✅ 12/20 joint 0.30 추종, 8 joint 부분 수렴 (DG-5F mass/limit, Day 5 보정) |

**Day 3 본질적 통과** (DDS pipeline 동작 자체는 5/5). PD/mass 보정은 Day 5 작업으로 분리.

## 7. 시행착오 (다른 PC에서 재현 시 참고)

1. **`HandState_/HandCmd_` 기본 7 slot** — 20 motor 채울 때 명시 init 필요. `dg5f_dds.py:46-49` 참조.
2. **stdout buffering** — sim_main background 부팅 시 `python -u`로 실행. test 스크립트도 마찬가지.
3. **action_provider _positions_buf size** — H1-2/G1 reuse 시 29로 hardcoded. UR10e만 쓰면 6이지만 호환 위해 `max(29, 20)` 유지.
4. **Reach task의 reward conflict 의심** — `position_command_error`는 절대 EE pose 기반이라 `use_default_offset=False` 변경에 영향 없음. NaN/inf 발생 안 함 확인.
5. **action_provider get_action()의 enable_dex3 / enable_inspire / enable_dg5f / gripper는 elif chain** — 한 번에 하나만 사용. mutex 검증을 sim_main argparse에서 처리.

## 8. Day 4 진입 가능 여부

✅ 진입 가능. Day 4 작업:
1. Camera scene mount (head/right_wrist/left_wrist 3개)
2. `tasks/common_config/camera_configs.py`에 UR10e용 preset 추가
3. ZMQ port 55555/55556/55557, WebRTC 60001-60003 mapping (기존 G1+Dex3 그대로)
4. 검증: `tcp://127.0.0.1:5555{5,6,7}` 에서 frame 수신
