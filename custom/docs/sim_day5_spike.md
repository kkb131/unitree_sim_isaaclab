# Day 5 Spike — AMR platform + Ctrl+C wrapper fix + PD gain tuning

> Plan: [/root/.claude/plans/keen-zooming-mist.md](/root/.claude/plans/keen-zooming-mist.md) Day 5 섹션
> Branch: `feat/ur10e-dg5f-sim`
> Day 1-4 결과: [sim_day1_spike.md](sim_day1_spike.md), [sim_day2_spike.md](sim_day2_spike.md), [sim_day3_spike.md](sim_day3_spike.md), [sim_day4_spike.md](sim_day4_spike.md)

## 0. Scope

Day 3에서 미해결로 남았던 4건 처리:
1. `run_ur10e_dg5f.sh` 가 Ctrl+C로 안 멈추는 문제
2. `test_lowcmd_pub.py` 실행 시 arm이 ground와 충돌해 멈춤 (실배포는 1m AMR 위 mount)
3. `test_dg5f_pub.py` 의 thumb f1_2가 q=0.3 명령에 안 움직임
4. UR10e shoulder_lift settling time 부족 (Day 3에서 target=-1.0, measured=-0.752, err 0.248 rad)

## 1. 변경 파일

| 파일 | 변경 |
|---|---|
| [`custom/scripts/run_ur10e_dg5f.sh`](../scripts/run_ur10e_dg5f.sh) | sim_main을 background로 띄우고 `wait`, `trap INT/TERM`이 직접 child에 signal forwarding |
| [`custom/tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py`](../tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py) | `amr_platform` (kinematic cuboid 0.6 × 0.8 × 1.0 m) scene attribute 추가 + `robot init_pos=(0,0,1.0)` |
| [`custom/robots/ur10e.py`](../robots/ur10e.py) | arm PD gain 대폭 상향 (shoulder_lift kp 300→2500, damping per-joint) |
| [`custom/scripts/test_dg5f_pub.py`](../scripts/test_dg5f_pub.py) | `--pose fist/open` preset 추가 — DG-5F per-joint URDF limit를 존중하는 target vector |
| [`custom/scripts/test_ur10e_dg5f_boot.py`](../scripts/test_ur10e_dg5f_boot.py) | `args.enable_cameras = True` 자동 설정 (Day 4 cameras scene attach 후 boot test가 cameras flag 요구) |

upstream 수정 0건.

## 2. 핵심 발견 / 설계 결정

### 2.1 Ctrl+C가 안 먹는 이유

`run_ur10e_dg5f.sh` 가 `python -u sim_main.py "${ARGS[@]}"` 를 foreground synchronous로 실행하면, Ctrl+C 시 bash는 SIGINT를 자기 foreground process group(자식 포함)에 보내지만, python이 SIGINT 핸들러를 가지고 한참 cleanup하는 동안 bash는 child가 끝날 때까지 SIGINT를 무시하고 매달려있음. 결과적으로 사용자 입장에선 "Ctrl+C가 무반응".

**해결**: sim_main을 background `&`로 띄우고 `wait` + `trap '... kill -INT $SIM_PID ...' INT TERM` 패턴.
- bash는 wait 중에도 signal을 받아 trap 실행
- trap이 명시적으로 child python에 `kill -INT`
- wait 루프가 child가 실제 끝날 때까지 재진입
- `EXIT` trap에서 yaml 복원
- `set -e` 는 wait 동안만 잠깐 끔 (`wait` 가 signal-killed child의 128+sig 반환을 받으면 set -e 가 스크립트 abort 시킴)

검증: wrapper 부팅 후 `kill -INT <wrapper_pid>` →
```
received signal 2, stopping controller...
[DDSActionProvider] ActionProvider stop
...
[run_ur10e_dg5f] restored original .../cam_config_server.yaml
```
+ `.ur10e.bak` 파일 없음 + sim_main, image_server 잔재 없음.

### 2.2 Ground collision: AMR pedestal 추가

`test_lowcmd_pub.py` 의 default target `[0, -1.0, 1.2, -1.2, -1.5, 0]` 는 init pose `shoulder_lift=-1.57` 에서 shoulder를 위로 -1.0 까지 회전(약 33°)시키는데, **이미 wrist + forearm + DG-5F 무게(~3kg, 모먼트 ~30Nm)가 shoulder_lift에 걸려있어 -1.0 으로 도달하기 전에 forearm + wrist가 ground 평면 (z=0)에 접촉 → arm이 jam**.

실배포는 1m 높이 AMR 위에 UR10e를 볼트로 고정. sim도 동일하게:

```python
PLATFORM_HEIGHT = 1.0
amr_platform = RigidObjectCfg(
    prim_path="/World/envs/env_.*/AMRPlatform",
    spawn=sim_utils.CuboidCfg(
        size=(0.6, 0.8, PLATFORM_HEIGHT),
        rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),  # 정적 fixture
        collision_props=sim_utils.CollisionPropertiesCfg(),
        visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.3,0.3,0.4)),
    ),
    init_state=RigidObjectCfg.InitialStateCfg(pos=(0.0, 0.0, PLATFORM_HEIGHT/2)),
)
robot = UR10ERobotPresets.ur10e_dg5f(init_pos=(0.0, 0.0, PLATFORM_HEIGHT))
```

`kinematic_enabled=True` 가 핵심 — 동역학 시뮬레이션엔 참여 안 함 (gravity로 떨어지지도, 외력에 흔들리지도 않음). 충돌 기하만 제공.

front_camera는 articulation의 `world` body에 parented 되어 있어 robot이 1m 위로 올라가도 카메라도 함께 이동, 상대 시야 유지. mount offset 변경 불필요.

### 2.3 DG-5F joint limit 비대칭 — f1_2 q=0.3 stuck 원인

`dg5f_right.urdf` 의 각 joint limit:

| joint | lower | upper | 의미 |
|---|---|---|---|
| rj_dg_1_1 | -0.384 | 0.890 | thumb 외전 |
| **rj_dg_1_2** | **-π** | **0.0** | **thumb 굴곡 — POSITIVE q는 limit 위반** |
| rj_dg_1_3, 1_4 | -π/2 | π/2 | thumb |
| rj_dg_2_1, 3_1, 4_1 | ~±0.5 | ~±0.5 | 손가락 외전 |
| rj_dg_{2,3,4}_2 | 0.0 | ~2.0 | 손가락 굴곡 — POSITIVE 굴곡 |
| rj_dg_5_1 | -0.017 | 1.047 | pinky 외전 (positive abduct) |
| rj_dg_5_2 | -0.419 | 0.611 | pinky 굴곡 |
| _3, _4 모두 | -π/2 | π/2 | 손가락 분절 |

**핵심**: thumb (f1)의 _2 joint만 굴곡 방향이 **negative**. 다른 손가락 _2는 positive 굴곡. Day 3의 `q=0.3` 일괄 publish 는 thumb f1_2 에 limit 위반 명령을 보낸 것이고, sim이 limit clamp해 0에서 안 움직임. **sim bug 아님 — joint convention 불일치**.

해결: `test_dg5f_pub.py` 에 `--pose fist/open` preset 추가. fist 는 limit을 모두 존중하는 valid target vector:
```python
FIST_POSE = [
    0.0, -1.0, 0.5, 0.5,   # thumb f1: f1_2 만 negative
    0.0,  1.0, 0.5, 0.5,   # index f2
    0.0,  1.0, 0.5, 0.5,   # middle f3
    0.0,  1.0, 0.5, 0.5,   # ring f4
    0.5,  0.3, 0.5, 0.5,   # pinky f5
]
```

xr_teleop docker 측에서 dex_retargeting → DDS publish 할 때도 동일하게 thumb f1_2 sign convention 인지하고 publish 해야 함.

### 2.4 UR10e PD gain 보정

Day 3/Day 5 초반 측정:
- shoulder_lift target=-1.0 → measured -0.6 ~ -0.75 (gravity 견딤 부족)
- elbow target=1.2 → measured 1.35 (overshoot/under-shoot)

원인: 기존 `kp=300, kd=8` (모든 arm joint 균등) 은 6-DoF 산업 로봇 wrist 무게(33kg arm + 1kg 핸드 + payload)에 비해 절대 부족. 문헌상 UR10e 류 6-DoF arm 시뮬에서 shoulder/elbow kp 1000-3000 N·m/rad 가 일반적.

새 gain (per-joint):

| joint | kp (old → new) | kd (old → new) |
|---|---|---|
| shoulder_pan | 300 → **1000** | 8 → **50** |
| shoulder_lift | 300 → **2500** | 8 → **80** |
| elbow | 250 → **1500** | 8 → **60** |
| wrist_1 | 150 → **500** | 8 → **25** |
| wrist_2 | 150 → **300** | 8 → **20** |
| wrist_3 | 150 → **200** | 8 → **15** |

damping 은 `kd ≈ 2·sqrt(kp·J_eff)` 비례 (critical-damping 근사). 오실레이션 없이 settling.

### 2.5 boot test (`test_ur10e_dg5f_boot.py`) cameras flag

Day 4 이후 scene에 `front_camera`, `right_wrist_camera` 가 있어 standalone boot test가 그냥 실행되면 `RuntimeError: A camera was spawned without the --enable_cameras flag` 로 죽음. test script에 `args.enable_cameras = True` 1줄 추가 — boot test는 항상 cameras 켜고 실행 (rendering offscreen).

## 3. 검증 결과

### 3.1 Ctrl+C / SIGINT cleanup

```
$ ./custom/scripts/run_ur10e_dg5f.sh --headless
[run_ur10e_dg5f] patched left_wrist_camera enable_zmq/webrtc → false
[run_ur10e_dg5f] launching sim_main... (Ctrl+C to stop)
...
========= start controller success =========
^C   ← Ctrl+C (또는 외부에서 kill -INT <wrapper_pid>)
[run_ur10e_dg5f] forwarding SIGINT → sim_main (pid=...)
received signal 2, stopping controller...
[DDSActionProvider] ActionProvider stop
...
cleanup completed
[run_ur10e_dg5f] restored original .../cam_config_server.yaml
```

검증 후 상태:
- `pgrep -af sim_main` → 결과 없음
- `pgrep -af image_server` → 결과 없음
- `ls teleimager/cam_config_server.yaml*` → `.ur10e.bak` 없음 (yaml만)

✅ PASS

### 3.2 Ground collision (test_lowcmd_pub.py)

```
$ python custom/scripts/test_lowcmd_pub.py --duration 5.0
publishing 100 LowCmd_ msgs to rt/lowcmd, targets=[0.0, -1.0, 1.2, -1.2, -1.5, 0.0]
publish done — verifying rt/lowstate tracking...
  targets : [0.0, -1.0, 1.2, -1.2, -1.5, 0.0]
  measured: [-0.0, -0.959, 1.232, -1.198, -1.501, -0.001]
  abs err : [0.0, 0.041, 0.032, 0.002, 0.001, 0.001]

UR10e arm tracking PASS (all err < 0.05 rad): True
```

비교 (Day 3, 기존 cfg, no platform): `measured: [..., -0.752, ...]`, 0.248 rad err
비교 (Day 5 platform only, old PD): `measured: [..., -0.6, ...]`, 0.4 rad err
**Day 5 platform + new PD**: `measured: [..., -0.959, ...]`, **0.041 rad err** ✅

6/6 joint < 0.05 rad. ✅ PASS

### 3.3 DG-5F fist pose (test_dg5f_pub.py --pose fist)

20 joint 별 추적:

```
f1_1: tgt=+0.00  meas=+0.012  err=0.012
f1_2: tgt=-1.00  meas=-0.998  err=0.002    ← thumb 굴곡, negative target
f1_3: tgt=+0.50  meas=+0.504  err=0.004
f1_4: tgt=+0.50  meas=+0.500  err=0.000
f2_1: tgt=+0.00  meas=-0.000  err=0.000
f2_2: tgt=+1.00  meas=+0.996  err=0.004    ← index 굴곡, positive target
...
f5_4: tgt=+0.50  meas=+0.499  err=0.001

max err = 0.012, joints out of tolerance: 0/20
PASS (max err < 0.05): True
```

20/20 joint < 0.05 rad. ✅ PASS

비교 (Day 5 초반, `--q 0.3` 균등): f1_2 만 0.000 stuck (limit clamp), 나머지 19개는 PASS.

### 3.4 boot test

```
$ python custom/scripts/test_ur10e_dg5f_boot.py --headless --num_steps 30
=== Articulation enumeration ===
body_names (27):
joint_names (26):
DEFAULT_EE_BODY 'wrist_3_link' in body_names: True
PASS — 30 steps executed without crash
```

scene에 amr_platform 추가 후에도 articulation 26 joint 유지, EE body `wrist_3_link` 변동 없음. ✅ PASS

## 4. Day 5 통과 기준 (4개)

| # | 항목 | 결과 |
|---|---|---|
| 1 | run wrapper Ctrl+C로 cleanly 종료 (yaml 복원, child process 정리) | ✅ |
| 2 | UR10e arm 6 joint 모두 target 추종 err < 0.05 rad | ✅ (max 0.041) |
| 3 | DG-5F 20 joint 모두 fist target 추종 err < 0.05 rad | ✅ (max 0.012) |
| 4 | platform 추가 후 boot test 26 joint 유지 + 30 step crash-free | ✅ |

✅ Day 5 4/4 PASS.

## 5. 시행착오 (다른 PC 재현 시 참고)

1. **AMR platform 추가 후 reach task의 EE workspace 시각화가 잘못된 위치에 뜸** — `CommandsCfg.ee_pose.ranges.pos_z=(0.4, 0.8)` 는 world frame이라 robot이 z=1.0에 있으면 시각화 target이 platform 안에 박힘. Day 5는 RL 학습 안 하므로 그대로 둠. 학습 단계에서 `pos_z=(1.4, 1.8)` 로 +PLATFORM_HEIGHT shift 필요.

2. **f1_2 stuck on q=0.3** — thumb only 음의 굴곡 방향. URDF limit 검사하면 즉시 보임. xr_teleop 측 retargeter에서도 thumb f1_2 sign 처리 필요.

3. **UR10e arm 진동 (overshoot ringing)** — damping 너무 낮음. 새 PD gain은 shoulder/elbow kd 60-80 으로 ~critically-damped. 만약 envelope이 안정적이지 않으면 damping ×1.5 후 재시도.

4. **`set -e` + `wait` 충돌** — bash `set -e` 켜진 상태에서 `wait $pid` 는 child가 signal-killed 시 exit 128+sig 받아 스크립트가 abort됨 → trap이 EXIT trap 실행하기 전에 die. 해결: wait 루프만 `set +e`, 끝나면 `set -e`. wrapper script line 75-83 참고.

5. **standalone boot test crash with cameras** — Day 4 후 scene에 cameras 있어 `RuntimeError: A camera was spawned without the --enable_cameras flag`. test script 자체에 `args.enable_cameras = True` 자동 설정. 단, cameras flag는 rendering 활성화하므로 boot test가 ~10s 느려짐.

## 6. Day 6 / 다음 단계

Day 5로 sim build 5-day plan 완료. 남은 작업:

- **종합 verification (가이드 §6 7개 항목)**: 모든 통과 항목 정리해서 xr_teleop docker user에게 보고
  - Day 2: boot ✅
  - Day 3: rt/lowstate / rt/dg5f/state pub ✅, rt/lowcmd 추종 ✅, rt/dg5f/cmd 추종 ✅
  - Day 4: ZMQ 3 cameras (left_wrist 의도적 disable) ✅, WebRTC 2 streams ✅
- 보고서 작성: `custom/docs/sim_build_complete_report.md` (가이드 §6 형식)
- xr_teleop docker로 회신 → Phase 2 / Week 4-6 / Gate 4 통과 조건의 sim 측 deliverable 완료

(선택) 추후 RL training 시도 시:
- CommandsCfg ee_pose 범위 +PLATFORM_HEIGHT shift
- DG-5F effort_limit / armature 실측치 (Tesollo official datasheet) 반영
- self_collisions 검토 (현재 disabled)
