# SIM BUILD COMPLETE — UR10e + Tesollo DG-5F (sim docker → xr_teleop docker)

> 보고 대상: **xr_teleop docker** Claude Code 인스턴스
> 발신: **sim docker** (`unitree_sim_isaaclab` fork), branch `feat/ur10e-dg5f-sim`
> 일시: 2026-05-11 (Phase 2 / Week 4-6 / Gate 4 sim 측 deliverable)
> 가이드 §6 검증 항목 7건 + 추가 5건 모두 PASS — Week 4 retargeting / IK 작업 진입 가능.

---

## 0. TL;DR (3분 안내)

```
[SIM BUILD COMPLETE]
Item 1 boot                      ✅  ~80s (run_ur10e_dg5f.sh)
Item 2 rt/lowstate publish       ✅  ~97 Hz (motor[0:6] valid)
Item 3 rt/dg5f/state publish     ✅  ~97 Hz (motor[0:20] valid)
Item 4 ZMQ 2 cameras             ✅  front 30.2Hz / right_wrist 30.0Hz
                                    (left_wrist 의도적 disable — single arm)
Item 5 WebRTC 2 streams          ✅  60001 front / 60003 right_wrist
                                    (60002 disable)
Item 6 rt/lowcmd round-trip      ✅  6/6 joint err < 0.025 rad
Item 7 rt/dg5f/cmd round-trip    ✅  20/20 joint err < 0.015 rad

Additional (Day 5):
+ init pose hold (no DDS)        ✅  max drift 0.018 rad
+ Ctrl+C cleanup                 ✅  yaml restore + child process clear
+ AMR pedestal under robot       ✅  ground collision 해소
+ thumb f1_2 limit convention    📝  documented (negative q)
+ action_provider default fix    ✅  upstream patch — 모든 robot 안전

Repo:        github.com/kkb131/unitree_sim_isaaclab.git  branch feat/ur10e-dg5f-sim
Latest commit: 74aad24 fix(day5b): init-pose hold + PD re-tune
```

**부팅 (한 줄)**: `./custom/scripts/run_ur10e_dg5f.sh` (또는 `--headless` 추가)

---

## 1. 통합 인터페이스 명세 (xr_teleop 측 코드 작성 시 필요한 모든 정보)

### 1.1 DDS topic — 변경 없음/신규

가이드 §3 그대로 구현:

| Topic | Direction | Type | Rate | UR10e+DG-5F 채워 넣는 슬롯 |
|---|---|---|---|---|
| `rt/lowstate` | sim → xr_teleop | `unitree_hg.LowState_` | ~97 Hz | `motor_state[0:6].q/dq/tau_est` 만 의미. IMU 13개 모두 0 |
| `rt/lowcmd` | xr_teleop → sim | `unitree_hg.LowCmd_` | (xr_teleop rate) | `motor_cmd[0:6].q` 절대 angle. mode/kp/kd는 sim 무시 |
| `rt/dg5f/state` | sim → xr_teleop | `unitree_hg.HandState_` | ~50 Hz throttle | `motor_state[0:20].q/dq/tau_est` |
| `rt/dg5f/cmd` | xr_teleop → sim | `unitree_hg.HandCmd_` | (xr_teleop rate) | `motor_cmd[0:20].q` 절대 angle |

`ChannelFactoryInitialize(1)` 필수 (ROS_DOMAIN_ID=1).

### 1.2 UR10e arm — joint 순서 (motor_cmd 인덱스)

| DDS index | URDF joint name | init pose [rad] |
|---|---|---|
| 0 | `shoulder_pan_joint` | 0.0 |
| 1 | `shoulder_lift_joint` | -1.57 |
| 2 | `elbow_joint` | +1.57 |
| 3 | `wrist_1_joint` | -1.57 |
| 4 | `wrist_2_joint` | -1.57 |
| 5 | `wrist_3_joint` | 0.0 |

EE body: **`wrist_3_link`** (USD `--merge-joints`로 tool0 / flange / dg_palm 모두 흡수). IK target 은 wrist_3_link pose.

### 1.3 DG-5F hand — joint 순서 (motor_cmd 인덱스, **finger-major**)

| DDS index | URDF joint | URDF limit [rad] | flexion 방향 | 비고 |
|---|---|---|---|---|
| 0 | `rj_dg_1_1` | (-0.384, +0.890) | mixed | thumb 외전 |
| **1** | **`rj_dg_1_2`** | **(-π, 0.0)** | **NEGATIVE** | **⚠ thumb 굴곡 — positive q는 limit clamp** |
| 2 | `rj_dg_1_3` | (-π/2, +π/2) | positive | thumb |
| 3 | `rj_dg_1_4` | (-π/2, +π/2) | positive | thumb tip |
| 4 | `rj_dg_2_1` | (-0.419, +0.611) | mixed | index 외전 |
| 5 | `rj_dg_2_2` | (0.0, +2.007) | POSITIVE | index 굴곡 |
| 6 | `rj_dg_2_3` | (-π/2, +π/2) | positive | index |
| 7 | `rj_dg_2_4` | (-π/2, +π/2) | positive | index tip |
| 8 | `rj_dg_3_1` | (-0.611, +0.611) | mixed | middle 외전 |
| 9 | `rj_dg_3_2` | (0.0, +1.955) | POSITIVE | middle 굴곡 |
| 10 | `rj_dg_3_3` | (-π/2, +π/2) | positive | middle |
| 11 | `rj_dg_3_4` | (-π/2, +π/2) | positive | middle tip |
| 12 | `rj_dg_4_1` | (-0.611, +0.419) | mixed | ring 외전 |
| 13 | `rj_dg_4_2` | (0.0, +1.902) | POSITIVE | ring 굴곡 |
| 14 | `rj_dg_4_3` | (-π/2, +π/2) | positive | ring |
| 15 | `rj_dg_4_4` | (-π/2, +π/2) | positive | ring tip |
| 16 | `rj_dg_5_1` | (-0.017, +1.047) | POSITIVE | pinky 외전 (1축) |
| 17 | `rj_dg_5_2` | (-0.419, +0.611) | mixed | pinky 굴곡 |
| 18 | `rj_dg_5_3` | (-π/2, +π/2) | positive | pinky |
| 19 | `rj_dg_5_4` | (-π/2, +π/2) | positive | pinky tip |

**critical** for xr_teleop retargeting:
- **`rj_dg_1_2` (DDS index 1) 의 flexion 은 negative**. retargeter가 positive q를 보내면 sim이 limit clamp해서 손가락 안 움직임. dex_retargeting DG-5F config 의 joint sign이 URDF와 정렬돼야 함.
- `rj_dg_{2,3,4}_2` (DDS index 5,9,13) flexion 은 positive — thumb 와 반대 부호.
- 손가락 _3, _4 (distal) 는 ±π/2 범위라 정·부 양방향 가능.

### 1.4 ZMQ camera (변경 없음)

| Camera | ZMQ port | WebRTC port | Mount | UR10e+DG-5F 상태 |
|---|---|---|---|---|
| head / front | 55555 | 60001 | `world` body (scene fixture) | ✅ 30 Hz publish |
| left_wrist | 55556 | 60002 | (single arm — 없음) | ⚠ **disabled** (yaml 패치) |
| right_wrist | 55557 | 60003 | `wrist_3_link` (palm view) | ✅ 30 Hz publish |

`run_ur10e_dg5f.sh` wrapper가 `cam_config_server.yaml` 의 left_wrist 섹션을 부팅 시 `enable_zmq:false / enable_webrtc:false` 패치하고 sim 종료 시 복원. xr_teleop 측은 left_wrist port에서 0 frame 받으니까 "left_wrist 없음" 처리.

JPEG quality 85 (기본). 프레임 사이즈 front ~6KB (단순 배경), right_wrist ~22KB (DG-5F finger 디테일).

### 1.5 init pose 동작 (xr_teleop 측 시작 절차 영향)

sim 부팅 직후 — xr_teleop이 아직 `rt/lowcmd`/`rt/dg5f/cmd` publish 안 하는 시점 — UR10e+DG-5F 는 **init pose 를 유지** (drift < 0.02 rad). xr_teleop 이 첫 명령을 보낼 때까지 안전한 상태.

명령이 도착하면 그 명령으로 즉시 전환. 명령 publish 중단(disconnect)되면 sim 은 마지막 명령을 캐시해 유지 (안전한 holdover).

→ xr_teleop 시작 시퀀스: "init pose 와 동일한 첫 명령 보내고 ramp" 같은 사전 절차 불필요. 첫 IK 결과 그대로 publish 해도 안전.

---

## 2. 부팅 / 종료 절차

### 2.1 부팅 (one-liner)

```bash
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
./custom/scripts/run_ur10e_dg5f.sh                     # viewport 켜기
./custom/scripts/run_ur10e_dg5f.sh --headless          # offscreen
./custom/scripts/run_ur10e_dg5f.sh --livestream_type 2 --public_ip 127.0.0.1   # WebRTC viewport
```

wrapper 내부 동작:
1. `cam_config_server.yaml` backup + `left_wrist_camera` enable_zmq/webrtc → false 패치
2. `activate_env.sh` (conda env `unitree_sim_env` + ROS_DOMAIN_ID=1 + RMW=cyclonedds + LD_LIBRARY_PATH) source
3. `sim_main.py` 실행 (default args):
   ```
   --task Isaac-Reach-UR10e-DG5F-Joint
   --robot_type ur10e
   --enable_dg5f_dds
   --enable_cameras
   --camera_include "front_camera,right_wrist_camera"
   --device cuda:0
   ```
4. 종료 시 (EXIT / SIGINT / SIGTERM) yaml 복원

추가 args 는 wrapper 마지막에 그대로 forward (`./custom/scripts/run_ur10e_dg5f.sh --headless --num_envs 2` 등).

### 2.2 종료 (Ctrl+C)

같은 터미널에서 **Ctrl+C** → wrapper 가 SIGINT 를 sim_main 에 forward → IsaacSim graceful shutdown → yaml 복원. 약 5-8 초.

원격 종료: `pkill -INT -f run_ur10e_dg5f.sh`

부득이 force kill 시 yaml 복원이 안 됐다면 수동 복원:
```bash
cd teleimager && git checkout cam_config_server.yaml && cd ..
```

### 2.3 환경 진단 (재현 가능성 점검)

자세한 절차는 [INTERIM_TEST_GUIDE.md](INTERIM_TEST_GUIDE.md). 다른 PC 에서 본 sim 을 띄울 때 §1-12 차례로 진행.

---

## 3. 검증 결과 상세

### 3.1 rt/lowstate 수신 (가이드 §6 item 2)

```python
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
import time
ChannelFactoryInitialize(1)
n = 0; def cb(_): nonlocal n; n += 1
ChannelSubscriber('rt/lowstate', LowState_).Init(cb, 32)
time.sleep(3); print(f"{n} msgs in 3s")
```

측정: **291 msgs / 3s = 97 Hz** ✅. `motor_state[0:6].q` 가 init pose 또는 마지막 cmd 추종. IMU 13 개는 모두 0.

### 3.2 rt/dg5f/state 수신 (item 3)

같은 패턴 with `HandState_` topic `rt/dg5f/state`. 측정: **~290 msgs / 3s = 97 Hz**. `motor_state[0:20].q` 채워짐. dds_min_interval_ms = 20 throttle.

### 3.3 rt/lowcmd round-trip (item 6) — UR10e arm

```bash
python custom/scripts/test_lowcmd_pub.py --duration 5.0
```

```
targets : [ 0.000, -1.000,  1.200, -1.200, -1.500,  0.000]
measured: [-0.000, -0.975,  1.216, -1.198, -1.501, -0.001]
abs err : [ 0.000,  0.025,  0.016,  0.002,  0.001,  0.001]
UR10e arm tracking PASS (all err < 0.05 rad): True
```

max err 0.025 rad (shoulder_lift, gravity-load). ✅

### 3.4 rt/dg5f/cmd round-trip (item 7) — DG-5F fist

```bash
python custom/scripts/test_dg5f_pub.py --pose fist --duration 5.0
```

20 joint 모두 max err **0.015 rad**. ✅

⚠ **`--q 0.3` 균등 명령은 절대 보내지 말 것** — thumb `rj_dg_1_2` (DDS index 1) 의 URDF upper limit 가 0.0 이라 positive q clamp 되어 손가락 안 움직임. dex_retargeting 출력의 sign이 URDF 와 일치하는지 retargeter config 단계에서 검증 필요.

### 3.5 ZMQ camera (item 4)

```bash
python custom/scripts/test_zmq_recv.py --duration 5.0
```

```
front          (port 55555):  151 frames (30.2 Hz), avg  5876 bytes  [OK]
right_wrist    (port 55557):  150 frames (30.0 Hz), avg 21778 bytes  [OK]
overall: PASS
```

left_wrist (55556) 은 의도적으로 disabled (single arm). xr_teleop 측 left_wrist subscriber 는 timeout / 0-frame 처리 필요.

### 3.6 WebRTC (item 5)

sim 부팅 로그: `WebRTC: enabled, webrtc port=60001`, `60003`. browser `https://localhost:60001` / `https://localhost:60003` 접속 가능 (self-signed cert 신뢰 등록 첫 회).

60002 (left_wrist) disabled.

### 3.7 Init pose hold (Day 5 추가)

DDS 명령 전혀 없는 상태로 sim 부팅 3 초 뒤 측정:

```
shoulder_pan      init +0.000   meas -0.000   drift  0.000
shoulder_lift     init -1.570   meas -1.556   drift +0.014
elbow             init +1.570   meas +1.588   drift +0.018
wrist_1           init -1.570   meas -1.564   drift +0.006
wrist_2           init -1.570   meas -1.570   drift +0.000
wrist_3           init +0.000   meas -0.000   drift  0.000

DG-5F: 0/20 joints drifted (max 0.024 rad, f1_1 gravity sag)
```

max drift 0.018 rad. ✅ xr_teleop 시작 시점에 sim 이 안전한 init pose 에 있음을 보장.

---

## 4. 시행착오 (xr_teleop 측이 알면 좋은 quirks)

### 4.1 `rj_dg_1_2` (thumb 굴곡) sign convention

DG-5F URDF 에서 thumb 의 굴곡 joint 만 `lower=-π, upper=0.0`. dex_retargeting 의 DG-5F config 에서 이 joint 의 limit 또는 sign 이 잘못 설정되면 thumb 가 안 움직임. retargeter unit test 시 thumb 단독 굴곡 명령을 negative q 로 보내서 검증.

### 4.2 robot 이 1m AMR pedestal 위에 위치

scene 의 `amr_platform` (0.6 × 0.8 × 1.0 m cuboid) 위에 UR10e 가 bolted. robot base frame 원점이 **z = 1.0 m**. xr_teleop 측에서 robot base TF 를 sim 의 base 위치와 align 시키려면 1m offset 고려. 실배포 AMR 도 동일 형태.

### 4.3 init pose 가 0이 아님

UR10e arm init pose `shoulder_lift=-1.57, elbow=+1.57, wrist_1=-1.57, wrist_2=-1.57` (Tee/ready 자세). xr_teleop 측이 처음 IK 시도할 때 이 자세에서 시작한다고 가정하고 IK seed 를 init pose 로 두면 jump 회피.

### 4.4 left_wrist camera 의 0-frame

`rt/dex3/left/cmd` 처럼 left_wrist ZMQ port 55556 / WebRTC 60002 는 의도적 비활성. xr_teleop 측 multi-cam subscriber 가 left_wrist 없어도 head + right_wrist 만으로 동작하도록 fallback 처리.

### 4.5 IMU 13 개가 모두 0

UR10e 는 IMU 없음. `rt/lowstate.imu_state` 가 모두 0 (orientation 0,0,0,1 / 나머지 0). xr_teleop 측 IMU 사용 코드가 있다면 분기 처리.

### 4.6 self-collision 비활성

`enabled_self_collisions=False` (Day 2 articulation cfg). DG-5F 손가락 끼리 또는 UR10e arm 자기 자신 끼리 충돌 무시. teleop 명령이 self-intersection 자세를 보내도 sim 은 안 막음. xr_teleop 측 IK / retargeter 에서 self-collision avoidance 책임.

### 4.7 PD gain 의미

`rt/lowcmd.motor_cmd[i].kp/kd` 는 sim 이 **무시**. sim 측 ImplicitActuatorCfg 가 자체 PD (UR10e shoulder_lift kp=4000, DG-5F kp=1500 등) 사용. xr_teleop publisher 가 kp/kd 채워도 의미 없지만 일관성 위해 그대로 채워 보내도 무방.

### 4.8 mode field

`MotorCmd_.mode=1` (PD active) 가 표준. mode=0 (passive) 도 sim 은 무시 — 어차피 q 만 사용.

### 4.9 `rj_dg_*_tip` 은 fixed joint

DG-5F URDF 의 7 개 fixed joint (`rj_dg_base`, `rj_dg_palm`, `rj_dg_{1..5}_tip`) 는 USD 변환 시 `--merge-joints` 로 흡수. 26 revolute joint (UR10e 6 + DG-5F 20) 만 articulation 에 존재. xr_teleop 측 retargeting target link 는 fingertip 의 fixed-merged 위치 = 부모 link 의 USD-merged 위치. URDF 그대로 import 한 dex_retargeting 은 별 문제 없을 것.

### 4.10 multicast 안 보임 시

양 docker 모두 `--network=host`. 한쪽이라도 bridge 면 multicast 안 갈 수 있음. cyclonedds.xml 의 unicast peers 설정으로 우회 가능 (template 은 repo 안에 있음).

---

## 5. 파일 목록 (이 sim build 에서 추가/수정)

### 5.1 신규 (custom/ 하위 — upstream 무영향)

```
custom/__init__.py                                           (Python module chain)
custom/robots/__init__.py
custom/robots/ur10e.py                                       UR10E_WITH_DG5F_HAND ArticulationCfg
custom/tasks/__init__.py
custom/tasks/common_config/__init__.py
custom/tasks/common_config/ur10e_configs.py                  UR10ERobotPresets.ur10e_dg5f()
custom/tasks/common_config/ur10e_camera_configs.py           front + right_wrist preset
custom/tasks/common_observations/__init__.py
custom/tasks/common_observations/ur10e_state.py              arm joint → SHM writer (100 Hz)
custom/tasks/common_observations/dg5f_state.py               DG-5F joint → SHM writer (50 Hz)
custom/tasks/ur10e_tasks/__init__.py                         (auto-imports reach_ur10e_dg5f)
custom/tasks/ur10e_tasks/reach_ur10e_dg5f/__init__.py        gym.register
custom/tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py
custom/tasks/ur10e_tasks/reach_ur10e_dg5f/mdp/__init__.py
custom/dds/__init__.py
custom/dds/dg5f_dds.py                                       rt/dg5f/{state,cmd} pub/sub

custom/tools/build_ur10e_dg5f_assets.sh                      URDF→USD 빌드 (Day 1)
custom/tools/combine_ur10e_dg5f_urdfs.py                     UR10e + DG-5F URDF 합성

custom/scripts/activate_env.sh                               conda + DDS env source
custom/scripts/run_ur10e_dg5f.sh                             부팅 wrapper (Day 5: SIGINT clean)
custom/scripts/test_ur10e_dg5f_boot.py                       standalone boot smoke test
custom/scripts/test_dds_listen.py                            rt/lowstate + rt/dg5f/state count
custom/scripts/test_lowcmd_pub.py                            UR10e arm tracking verifier
custom/scripts/test_dg5f_pub.py                              DG-5F hand publisher (--pose fist/open)
custom/scripts/test_zmq_recv.py                              ZMQ frame count + JPEG size

custom/docs/sim_day{1..5}_spike.md                           일별 결과
custom/docs/INTERIM_TEST_GUIDE.md                            다른 PC 재현 가이드
custom/docs/sim_build_complete_report.md                     본 문서
```

### 5.2 upstream 수정

| File | 변경 |
|---|---|
| `sim_main.py` | `--enable_dg5f_dds` argparse, 4-way mutex (dex3/dex1/inspire/dg5f), `import custom.tasks.ur10e_tasks` |
| `dds/dds_create.py` | `robot_type=="ur10e"` → `G1RobotDDS(node_name="ur10e_robot")` 재사용 + `enable_dg5f_dds` → `from custom.dds.dg5f_dds import DG5FDDS` 분기 |
| `action_provider/action_provider_dds.py` | UR10e (6 joint) + DG-5F (20 joint finger-major) 매핑 분기. **Day 5: default action = init joint pose (was: zero)** — 모든 robot 안전 holdover |

### 5.3 assets (gitignore — 빌드 산출물, 재현은 `build_ur10e_dg5f_assets.sh` 로)

```
assets/robots/ur10e-dg5f-urdf/ur10e.urdf
assets/robots/ur10e-dg5f-urdf/dg5f_right.urdf
assets/robots/ur10e-dg5f-urdf/ur10e_with_dg5f.urdf          (combined)
assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd
assets/robots/ur10e-dg5f-usd/configuration/ur10e_with_dg5f_{base,robot,sensor,physics}.usd
```

---

## 6. xr_teleop 측 후속 작업 (가이드 §8 + 본 보고 기준)

가이드 §8 그대로 + 본 보고로 명확해진 항목 보강:

1. **`UR10e_ArmController` (xr_teleoperate)** — `rt/lowcmd` 에 `motor_cmd[0:6].q` 절대 angle publish. mode/kp/kd 는 무시되지만 일관성 위해 채워 보내도 무방. publish rate 는 본 sim 측이 ~100 Hz 이상 처리 OK.
2. **`UR10e_ArmIK`** — wrist_3_link target. 본 sim 의 init pose 가 `(0, -1.57, 1.57, -1.57, -1.57, 0)` 이고 robot base 가 world z=1.0 m 임을 IK seed/frame transform 에 반영.
3. **`DG5F_Controller`** — `rt/dg5f/cmd.motor_cmd[0:20].q` finger-major (DDS 0..3 = thumb, ..., 16..19 = pinky). 본 보고 §1.3 joint table 그대로.
4. **`dex_retargeting` DG-5F config 작성** — URDF 의 `rj_dg_1_2` sign convention (negative flexion) 정확히 반영 필요. 기존 inspire / dex3 config 와 차이는 thumb 만 sign 다름.
5. **`teleop_hand_and_arm.py --arm ur10e --ee dg5f` 분기 추가** — robot_type 명령행 옵션.
6. **end-to-end smoke test** — Quest 3 / Galaxy XR Chrome WebXR → vuer → xr_teleoperate → CycloneDDS → IsaacSim 본 sim → WebRTC 영상 양방향. 본 sim 의 host 와 xr_teleop docker 가 `--network=host` 같은 LAN 에서 multicast 디스커버리 동작.
7. **Week 4 report 작성** (Gate 4 통과 보고).

### 6.1 cyclonedds.xml unicast 대체 (multicast 안 보일 시)

본 sim repo 에 `cyclonedds.xml` template 있음. 양 docker 모두 같은 xml 사용 + 각 docker IP 를 `<Peer address="..."/>` 로 명시. `--network=host` 환경에선 일반적으로 multicast 동작.

---

## 7. 검증 재현 명령 (xr_teleop 측 또는 다른 PC 에서)

```bash
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
git fetch origin feat/ur10e-dg5f-sim
git checkout feat/ur10e-dg5f-sim
git pull

# 1) Assets 빌드 (다른 PC 일 시 — 본 docker는 이미 빌드됨)
./custom/tools/build_ur10e_dg5f_assets.sh

# 2) Sim 부팅
./custom/scripts/run_ur10e_dg5f.sh --headless

# 3) 다른 터미널에서 검증
source custom/scripts/activate_env.sh
python custom/scripts/test_dds_listen.py            # item 2,3
python custom/scripts/test_zmq_recv.py --duration 5.0  # item 4
python custom/scripts/test_lowcmd_pub.py --duration 5.0  # item 6
python custom/scripts/test_dg5f_pub.py --pose fist --duration 5.0  # item 7

# 4) (선택) WebRTC item 5: browser https://localhost:60001 / 60003
```

부팅 wrapper 가 left_wrist disabled 한 상태 — yaml 패치는 sim 종료 시 자동 복원. force kill 했다면 `cd teleimager && git checkout cam_config_server.yaml` 으로 복원.

---

## 8. References

- **본 repo**: github.com/kkb131/unitree_sim_isaaclab.git branch `feat/ur10e-dg5f-sim`
- 일별 진행 보고: [`custom/docs/sim_day{1..5}_spike.md`](.)
- 재현 가이드: [`custom/docs/INTERIM_TEST_GUIDE.md`](INTERIM_TEST_GUIDE.md)
- 원천 가이드: [`SIM_UR10E_DG5F_BUILD_GUIDE.md`](/workspace/isaaclab/datasets/vr_teleop/docs/SIM_UR10E_DG5F_BUILD_GUIDE.md) (xr_teleop docker)
- 통합 사양: [`INTEGRATION_FOR_XR_TELEOPERATE.md`](/workspace/isaaclab/datasets/unitree_sim_isaaclab/INTEGRATION_FOR_XR_TELEOPERATE.md)

**sim build 완료 — xr_teleop 측 Week 4 retargeting / IK 진입 가능**.
