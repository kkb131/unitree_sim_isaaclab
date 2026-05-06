# sim_main.py 동작 원리 (초보자용 학습 자료)

대상 명령:

```bash
python sim_main.py \
  --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint \
  --enable_dex3_dds --robot_type g129 \
  --device cuda:0 --enable_cameras \
  --livestream_type 2 --public_ip 127.0.0.1
```

이 한 줄이 실행되는 약 80초 동안 무슨 일이 벌어지는지 — USD 로딩, DDS 통신,
이미지 서버, 메인 루프 — 단계별로 추적합니다. 코드 라인 번호를 함께 적어두니
파일을 같이 열어두고 따라 읽으세요.

---

## 1. CLI 옵션의 의미 (한눈에)

| 플래그 | 의미 |
|---|---|
| `--task Isaac-PickPlace-Cylinder-G129-Dex3-Joint` | gym 환경 ID. 어떤 로봇·씬·관찰·보상을 쓸지 결정 |
| `--enable_dex3_dds` | Dex3 (3-finger) 핸드를 DDS로 노출 (`rt/dex3/{left,right}/{state,cmd}`) |
| `--robot_type g129` | 로봇 패밀리 식별자. DDS 객체 등록 시 G1 토픽(`rt/lowstate`, `rt/lowcmd`) 활성화 |
| `--device cuda:0` | PhysX/렌더링이 GPU에서 동작 |
| `--enable_cameras` | head/left_wrist/right_wrist 카메라 텐서 출력 + image_server(ZMQ/WebRTC) 시작 |
| `--livestream_type 2` | Omniverse Kit 뷰포트 WebRTC 스트리밍 (0=없음, 1=public, 2=private) |
| `--public_ip 127.0.0.1` | WebRTC 클라이언트가 접속할 IP |

추가로 자주 쓰는 것:
- `--headless --no_render` — 화면/스트리밍 끄고 순수 시뮬만
- `--step_hz 100` — 메인 루프 목표 주기
- `--seed 42` — 환경 시드 (랜덤 위치 등)

---

## 2. 부팅 순서 (sim_main.py가 하는 일을 시간 순으로)

### 2.1 인터프리터 진입 ~ Kit 시작 (0–10초)

`sim_main.py` 최상단 ([sim_main.py:1–96](sim_main.py)):

1. `os.environ["PROJECT_ROOT"] = ...` — 다른 모듈이 에셋 경로를 만들 때 참조하는 루트
2. **import 순서가 중요**:
   - `from isaaclab.app import AppLauncher` (line 21) — Isaac Sim/Kit 부팅 도우미
   - `from teleimager.image_server import run_isaacsim_server` (line 23)
   - `from dds.dds_create import create_dds_objects, create_dds_objects_replay` (line 24)
3. `parser.parse_known_args()` 후 `AppLauncher(args_cli)` ([line 95](sim_main.py#L95)) 호출 — 이 시점에 **Omniverse Kit 커널이 부팅**됩니다. 콘솔에 `[7.687s] Simulation App Starting`, `Loading experience file: .../isaaclab.python.rendering.kit` 같은 메시지가 보이는 단계.
4. `simulation_app = app_launcher.app` — 이후 모든 Isaac Sim API가 사용 가능

> **왜 중요한가**: Kit이 부팅된 *뒤*에야 `isaacsim.*` / `omni.*` 모듈을 import할 수 있습니다. `sim_main.py`가 USD 관련 import를 미루는 이유.

### 2.2 환경 생성 — gym.make (10–90초의 대부분)

[sim_main.py:185](sim_main.py#L185): `env = gym.make(args_cli.task, cfg=env_cfg).unwrapped`

이 한 줄이 **시뮬레이션 셋업의 99%**입니다. 내부 흐름:

1. **task ID → config 클래스** 매핑이 import 시점에 등록됨
   - [tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/__init__.py](tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/__init__.py):
     ```python
     gym.register(
         id="Isaac-PickPlace-Cylinder-G129-Dex3-Joint",
         entry_point="isaaclab.envs:ManagerBasedRLEnv",
         kwargs={"env_cfg_entry_point": PickPlaceG129DEX3JointEnvCfg},
     )
     ```
2. `PickPlaceG129DEX3JointEnvCfg` ([pickplace_cylinder_g1_29dof_dex3_joint_env_cfg.py:119](tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/pickplace_cylinder_g1_29dof_dex3_joint_env_cfg.py#L119))이 `ManagerBasedRLEnvCfg`를 상속받아 **Scene / Actions / Observations / Terminations / Rewards / Events**를 한 곳에 모아둠
3. Isaac Lab의 `ManagerBasedRLEnv` 생성자가 cfg를 읽어서:
   - PhysX 초기화 (dt=0.005s, decimation=2 → 100Hz 제어)
   - **USD prim들을 Stage에 spawn** (다음 절에서 자세히)
   - 카메라/액션/관찰/보상 매니저 인스턴스 생성

콘솔에 `[INFO]: Time taken for scene creation : 2.78 seconds` → `Starting the simulation. This may take a few seconds...` → 약 80초 후 `[INFO]: Time taken for simulation start : 80.72 seconds` 나오는 단계.

### 2.3 이미지 서버 + DDS 객체 등록 (수 초)

[sim_main.py:377](sim_main.py#L377): `image_server = run_isaacsim_server()`
- [teleimager/cam_config_server.yaml](teleimager/cam_config_server.yaml)을 읽어 head/left_wrist/right_wrist 각각 ZMQ(55555/55556/55557) + WebRTC(60001/60002/60003) 서버 구동
- 카메라 프레임은 별도 비동기 큐에 들어가서 ZMQ pub로 흘러감 ([tasks/common_observations/camera_state.py](tasks/common_observations/camera_state.py))

[sim_main.py:384](sim_main.py#L384): `create_dds_objects(args_cli, env)`
- [dds/dds_create.py:5–53](dds/dds_create.py#L5)에서 `--robot_type` / `--enable_dex3_dds`에 따라 DDS 객체를 등록:
  - `g129` → `G1RobotDDS` (rt/lowstate publish, rt/lowcmd subscribe)
  - `dex3` → `Dex3DDS` (rt/dex3/{left,right}/state publish, .../cmd subscribe)
  - `reset_pose` → ResetPoseCmdDDS (rt/reset_pose/cmd subscribe)
  - `sim_state` → SimStateDDS (rt/sim_state publish)
  - `rewards` → RewardsDDS

`DDSManager`(싱글톤, [dds/dds_master.py:11](dds/dds_master.py#L11))가 모두 모아 관리.

### 2.4 Action provider + Controller 생성

[sim_main.py:402](sim_main.py#L402) `create_action_provider(env, args_cli)` — 기본 `dds`이면 [action_provider/action_provider_dds.py](action_provider/action_provider_dds.py)의 `DDSActionProvider`. 이 객체가 **`rt/lowcmd`/`rt/dex3/*/cmd`를 받아 Isaac Lab의 action 텐서로 변환**.

[sim_main.py:421](sim_main.py#L421) `RobotController(env, control_config)` — [layeredcontrol/robot_control_system.py](layeredcontrol/robot_control_system.py). 메인 루프에서 호출되는 `controller.step()`이 액션 가져와 `env.step(action)`을 실행하고 100Hz로 박자 맞춤.

### 2.5 백그라운드 스레드 시작 + 메인 루프

[sim_main.py:451](sim_main.py#L451) `controller.start()`:
- `dds_manager.start_publishing(...)` → publish 스레드 시작 ([dds/dds_master.py:140](dds/dds_master.py#L140))
- `dds_manager.start_subscribing(...)` → subscribe는 SDK 콜백 기반이라 별도 polling 스레드는 없음 (init 시 콜백만 등록)

[sim_main.py:461](sim_main.py#L461) 메인 루프:

```python
while simulation_app.is_running() and controller.is_running:
    env_state = env.scene.get_state()
    sim_state_dds.write_sim_state_data(...)          # 시뮬 상태 → DDS
    reset_pose_cmd = reset_pose_dds.get_reset_pose_command()  # 외부 reset 명령 처리
    controller.step()                                # 액션 받기 → env.step
```

`controller.step()` 내부 ([robot_control_system.py:95–148](layeredcontrol/robot_control_system.py#L95)):

```python
action = self.action_provider.get_action(self.env)   # rt/lowcmd로 받은 명령
self.env.step(action)                                # PhysX 1 tick + 카메라 렌더
# 100Hz가 되도록 sleep
```

---

## 3. 어떤 USD 파일이 로드되는가

`PickPlaceG129DEX3JointEnvCfg.scene` = `ObjectTableSceneCfg(TableCylinderSceneCfg)` 상속.

| Prim path | USD 경로 | 설명 |
|---|---|---|
| `/World/envs/env_*/Room` | `{ISAAC_NUCLEUS_DIR}/Environments/Simple_Warehouse/warehouse.usd` | Isaac Sim 공식 nucleus의 창고 환경 |
| `/World/envs/env_*/PackingTable` ~ `_6` | `assets/objects/PackingTable/PackingTable.usd` (×6 인스턴스) | 작업대 |
| `/World/envs/env_*/Robot` | **`assets/robots/g1-29dof-dex3-base-fix-usd/g1_29dof_with_dex3_base_fix.usd`** | G1 휴머노이드(29-DoF 몸통 + dex3 양손) |
| `/World/envs/env_*/Object` | (USD 아님 — `sim_utils.CylinderCfg(radius=0.018, height=0.35)`) | **절차적**으로 생성되는 실린더 (집어들 대상) |
| `/World/envs/env_*/Robot/camera_link/front_cam` | (PinholeCameraCfg, USD 아님) | 머리 카메라 |
| `/World/envs/env_*/Robot/left_hand_camera_base_link/left_wrist_camera` | 〃 | 왼손 손목 카메라 |
| `/World/envs/env_*/Robot/right_hand_camera_base_link/right_wrist_camera` | 〃 | 오른손 손목 카메라 |

> 즉 USD로 로드되는 건 **로봇·테이블·창고** 셋이고, 실린더와 카메라는 코드에서 만들어집니다.

경로 정의 위치:
- 로봇 USD: [robots/unitree.py:11–13](robots/unitree.py#L11) (`G129_CFG_WITH_DEX3_BASE_FIX`)
- 씬: [tasks/common_scene/base_scene_pickplace_cylindercfg.py](tasks/common_scene/base_scene_pickplace_cylindercfg.py)
- 로봇 프리셋: [tasks/common_config/robot_configs.py:263](tasks/common_config/robot_configs.py#L263) (`g1_29dof_dex3_base_fix`)
- 카메라 프리셋: [tasks/common_config/camera_configs.py:87, 143, 159](tasks/common_config/camera_configs.py#L87)

다른 변형 태스크에서 실제로 다른 USD가 로드됨:
- `Inspire` 핸드 → `assets/robots/g1-29dof-inspire-base-fix-usd/g1_29dof_with_inspire_rev_1_0.usd`
- `Wholebody` → `assets/robots/g1-29dof_wholebody_dex3/g1_29dof_with_dex3_rev_1_0.usd` (waist 자유, 발이 풀림)
- H1-2 → `assets/robots/h1_2-26dof-inspire-base-fix-usd/h1_2_26dof_with_inspire_rev_1_0.usd`

---

## 4. Scene 그래프와 prim_path 패턴

Isaac Lab은 **multi-environment**(하나의 Stage에 같은 씬 N개 복제)를 지원하기 위해 prim path에 와일드카드를 씁니다:

```
/World
├── envs/
│   └── env_0/                       # num_envs=1이라 env_0만
│       ├── Room                     ← warehouse.usd
│       ├── PackingTable, _2 ... _6  ← PackingTable.usd ×6
│       ├── Object                   ← procedural Cylinder
│       └── Robot                    ← g1_29dof_with_dex3_base_fix.usd
│           ├── pelvis, torso_link, ...
│           ├── camera_link/front_cam
│           ├── left_hand_camera_base_link/left_wrist_camera
│           └── right_hand_camera_base_link/right_wrist_camera
└── (light, ground, ...)
```

config의 `prim_path="/World/envs/env_.*/Robot"`는 정규식 — `env_0/Robot`, `env_1/Robot`, … 모두 매치. `num_envs=1`이면 사실상 단일 인스턴스.

---

## 5. DDS 통신은 어떻게 동작하는가

### 5.1 큰 그림

```
   ┌─ Isaac Lab side (sim) ───────────────────────────────────┐
   │                                                          │
   │  env.step()  ──→  관절 상태/카메라/.. 텐서                  │
   │                       │                                  │
   │                       ▼                                  │
   │                  shared memory  (numpy/POSIX SHM)        │
   │                       │                                  │
   │                       ▼                                  │
   │  G1RobotDDS.dds_publisher()  ───→  CycloneDDS 메시지       │
   │                       │             (LowState_)           │
   └───────────────────────┼───────────────────────────────────┘
                           ▼
                ╭──── DDS bus (domain 1) ────╮
                ╰────┬───────────────────┬────╯
                     │                   │
                     ▼                   ▼
              rt/lowstate          rt/lowcmd
              (sim publishes)      (sim subscribes)
                     ▲                   │
                     │                   ▼
   ┌─────────────────┴──── xr_teleoperate / external client ─┐
   │  ChannelSubscriber("rt/lowstate", LowState_).Init(cb)   │
   │  ChannelPublisher ("rt/lowcmd",    LowCmd_).Write(cmd)  │
   └─────────────────────────────────────────────────────────┘
```

### 5.2 도메인 ID = 1 (도메인 0 아님!)

`sim_main.py`가 하는 일은 사실 매우 단순합니다 (메인 루프 안):
- DDSManager가 처음 만들어질 때 `_init_dds()`가 `ChannelFactoryInitialize(1)` 호출
- 이 1이 **DDS 도메인 ID**. 다른 클라이언트도 같은 도메인 1로 초기화해야 메시지가 오감

그래서 외부에서 검증할 때:

```python
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
ChannelFactoryInitialize(1)   # ← 1 필수
```

### 5.3 토픽 카탈로그

각 DDS 객체가 자기 `setup_publisher()` / `setup_subscriber()`에서 토픽 이름과 IDL 타입을 묶어둠.

| 토픽 | 방향 (sim 기준) | 타입 (`unitree_sdk2py.idl.*`) | 정의 위치 |
|---|---|---|---|
| `rt/lowstate` | publish | `unitree_hg.msg.dds_.LowState_` | [dds/g1_robot_dds.py:51](dds/g1_robot_dds.py#L51) |
| `rt/lowcmd` | subscribe | `unitree_hg.msg.dds_.LowCmd_` | [dds/g1_robot_dds.py:63](dds/g1_robot_dds.py#L63) |
| `rt/dex3/left/state` | publish | `unitree_hg.msg.dds_.HandState_` | [dds/dex3_dds.py:59](dds/dex3_dds.py#L59) |
| `rt/dex3/right/state` | publish | `unitree_hg.msg.dds_.HandState_` | [dds/dex3_dds.py:63](dds/dex3_dds.py#L63) |
| `rt/dex3/left/cmd` | subscribe | `unitree_hg.msg.dds_.HandCmd_` | [dds/dex3_dds.py:76](dds/dex3_dds.py#L76) |
| `rt/dex3/right/cmd` | subscribe | `unitree_hg.msg.dds_.HandCmd_` | [dds/dex3_dds.py:82](dds/dex3_dds.py#L82) |
| `rt/sim_state` | publish | `std_msgs.msg.dds_.String_` (JSON) | [dds/sim_state_dds.py:46](dds/sim_state_dds.py#L46) |
| `rt/reset_pose/cmd` | subscribe | `std_msgs.msg.dds_.String_` | [dds/reset_pose_dds.py](dds/reset_pose_dds.py) |
| `rt/run_command/cmd` | subscribe (Wholebody만) | `std_msgs.msg.dds_.String_` | [dds/commands_dds.py:46](dds/commands_dds.py#L46) |

### 5.4 Publisher 측 작동 흐름 (rt/lowstate 예시)

```
[Isaac Lab] env.step()
   │
   │   env.scene["robot"].data.joint_pos  →  numpy
   ▼
[shared_memory_manager] write_data(...)
   │
   │   POSIX shared memory "isaac_robot_state"
   ▼
[DDSManager._publish_loop]  (별도 스레드, ~100Hz)
   │   for name in pub_list:
   │       obj.dds_publisher()              ← G1RobotDDS.dds_publisher()
   ▼
[G1RobotDDS.dds_publisher]
   │   data = self.input_shm.read_data()
   │   for i in range(35):
   │       self.low_state.motor_state[i].q  = data["joint_pos"][i]
   │       self.low_state.motor_state[i].dq = data["joint_vel"][i]
   │       ...
   │   self.publisher.Write(self.low_state)
   ▼
[CycloneDDS] domain 1, 토픽 "rt/lowstate"  →  네트워크
```

핵심 포인트:
- **Isaac Lab 메인 스레드는 SHM 쓰기만** — DDS 직렬화는 별도 스레드에서. 시뮬 루프 지연 최소화.
- 발행 주기는 `DDSManager._default_pub_interval` 기본값(약 100Hz). 객체별로 `set_publish_rate(name, hz)`로 덮어쓸 수 있음.

### 5.5 Subscriber 측 작동 흐름 (rt/lowcmd 예시)

```
[xr_teleoperate]
   pub.Write(LowCmd_(motor_cmd=[...]))
   ▼
[CycloneDDS]  →  네트워크  →
   ▼
[G1RobotDDS.setup_subscriber] (init 시점에 등록)
   self.subscriber = ChannelSubscriber("rt/lowcmd", LowCmd_)
   self.subscriber.Init(cb, queue_len=32)
   ▼
[G1RobotDDS.dds_subscriber] (콜백, SDK 스레드에서 호출)
   data = {"q": [...], "kp": [...], "kd": [...], ...}
   self.output_shm.write_data(data)        ← "dds_robot_cmd" SHM
   ▼
[Isaac Lab 메인 루프]
   action = action_provider.get_action(env)
   ▼
[DDSActionProvider.get_action]
   data = self.input_shm.read_data()       ← "dds_robot_cmd"
   action = torch.tensor([data["q"][i] for i in mapping]).unsqueeze(0)
   return action
   ▼
[env.step(action)]   PD 컨트롤러가 q_target을 따라가게 토크 계산
```

핵심 포인트:
- **Sim과 외부 사이의 다리는 SHM**. DDS 콜백이 SHM 쓰고, 메인 루프가 SHM 읽음.
- DDS는 비동기인데 sim 루프는 동기 — SHM 덕분에 **마지막 명령** 이 다음 step에 자연스럽게 반영됨 (메시지를 놓쳐도 큰 문제 없음).

### 5.6 왜 ROS2 도구로 안 보이나

토픽 타입이 **raw CycloneDDS IDL** (Unitree가 정의한 IDL을 unitree_sdk2py가 컴파일한 것)이라 ROS 2의 IDL과 다릅니다. `ros2 topic list`는 ROS 2가 아는 노드만 봐서 `/parameter_events`, `/rosout`만 표시. 데이터 흐름 검증은 `unitree_sdk2py.ChannelSubscriber`로 해야 함.

---

## 6. 메인 루프 1 tick의 시간 분해

기본값 (cfg `__post_init__`에서):
- `sim.dt = 0.005s` → PhysX는 200Hz로 시간 진행
- `decimation = 2` → 액션은 2 PhysX step 마다 한 번 → **100Hz 제어**
- `step_hz = 100` (CLI 기본) → 메인 루프도 100Hz 목표

한 tick (10 ms) 안에서 일어나는 일:

```
t=0.0 ms   action_provider.get_action()    ← rt/lowcmd 마지막 값을 SHM에서 읽음
           env.step(action)
              └── PhysX 2 step (각 5 ms)
              └── 카메라 렌더 (decimation 주기마다)
              └── observation 계산 → SHM "isaac_robot_state" 쓰기
t=~7 ms    return action_time, env_time
t=~7-10ms  sleep으로 100Hz 맞춤
t=10 ms    next tick
```

병렬로 다른 스레드:
- `DDSManager._publish_loop` (별도 스레드) — `obj.dds_publisher()` 호출, SHM 읽어 DDS 발행
- 카메라 비동기 writer — 프레임 큐에서 꺼내 ZMQ pub 송신

콘솔에 주기적으로 뜨는 `=== While loop execution frequency statistics ===`는 이 메인 루프의 실제 측정 주파수.

---

## 7. 이미지 서버 (teleimager)

`--enable_cameras` 플래그가 있으면 [sim_main.py:377](sim_main.py#L377)에서 `run_isaacsim_server()`가 호출됨.

흐름:
1. [teleimager/cam_config_server.yaml](teleimager/cam_config_server.yaml) 읽기 (head/left_wrist/right_wrist 각각 ZMQ port + WebRTC port)
2. 카메라 별 publisher 객체 생성 — ZMQ `bind("tcp://0.0.0.0:55555")` 등
3. Isaac Lab observation 매니저가 매 tick마다 `get_camera_image(env)` 호출 → 카메라 텐서를 SHM/큐에 push
4. teleimager의 비동기 writer가 큐에서 꺼내 JPEG 인코딩(`--camera_jpeg`) 후 ZMQ pub
5. xr_teleoperate의 `image_client`가 같은 호스트(또는 LAN)에서 ZMQ sub로 수신

WebRTC 포트(60001 등)는 브라우저에서 직접 보는 용도. xr_teleoperate는 **ZMQ만** 사용.

> 참고: Isaac Sim 자체 WebRTC 뷰포트(`--livestream_type 2`로 켠 것)는 별개의 스트림. Kit 내부의 카메라 뷰가 8211 포트(시그널링)로 송출됨. 두 시스템은 같은 포트를 쓰지 않음.

---

## 8. 코드 지도 (어디를 보면 무엇이 있나)

| 알고 싶은 것 | 가야 할 파일 |
|---|---|
| 전체 진입점 + 메인 루프 | [sim_main.py](sim_main.py) |
| 태스크 = (씬+액션+관찰+보상) 정의 | [tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/pickplace_cylinder_g1_29dof_dex3_joint_env_cfg.py](tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/pickplace_cylinder_g1_29dof_dex3_joint_env_cfg.py) |
| 씬 (room/table/cylinder) | [tasks/common_scene/base_scene_pickplace_cylindercfg.py](tasks/common_scene/base_scene_pickplace_cylindercfg.py) |
| 로봇 USD 경로 | [robots/unitree.py](robots/unitree.py) |
| 로봇 초기 자세 / 관절 분류 | [tasks/common_config/robot_configs.py](tasks/common_config/robot_configs.py) |
| 카메라 부착 위치 | [tasks/common_config/camera_configs.py](tasks/common_config/camera_configs.py) |
| DDS 객체 등록 | [dds/dds_create.py](dds/dds_create.py) |
| 발행 스레드 / 주기 제어 | [dds/dds_master.py](dds/dds_master.py) |
| G1 state↔cmd 매핑 | [dds/g1_robot_dds.py](dds/g1_robot_dds.py) |
| Dex3 state↔cmd | [dds/dex3_dds.py](dds/dex3_dds.py) |
| 외부 명령을 action 텐서로 변환 | [action_provider/action_provider_dds.py](action_provider/action_provider_dds.py) |
| 100Hz 제어 루프 | [layeredcontrol/robot_control_system.py](layeredcontrol/robot_control_system.py) |
| 카메라 → SHM/ZMQ | [tasks/common_observations/camera_state.py](tasks/common_observations/camera_state.py), [teleimager/src/teleimager/image_server.py](teleimager/src/teleimager/image_server.py) |
| 보상 계산 | [tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/mdp/](tasks/g1_tasks/pick_place_cylinder_g1_29dof_dex3/mdp/) |
| 종료 조건 | 〃 (`reset_object_estimate`) |
| 리셋 명령 처리 | [dds/reset_pose_dds.py](dds/reset_pose_dds.py) + sim_main.py 메인 루프 |

---

## 9. 자주 묻는 질문

**Q1. `--num_envs`는 왜 1인가?**
실시간 텔레오퍼레이션 목적이라 병렬 환경이 필요 없습니다. 학습용 RL이라면 cfg에서 `num_envs`를 늘릴 수 있지만 USD prim path 와일드카드(`env_.*`)가 그에 맞춰 환경별 인스턴스를 만들어줍니다.

**Q2. 시뮬 시작에 80초가 걸리는데 왜?**
- Kit 부팅 + 셰이더 캐시 (~10s)
- USD 로딩(warehouse, 6×PackingTable, 로봇 — 메시 + 콜라이더 변환) (~5s)
- PhysX scene initialization + GPU pipeline 빌드 (~60s)
- 카메라 텐서 파이프라인 초기화 (~5s)

같은 컨테이너에서 두 번째 실행은 캐시 덕에 빨라집니다.

**Q3. PD 게인은 어디서 정해지나?**
`LowCmd_.motor_cmd[i].kp/kd`는 외부(xr_teleoperate)가 매 명령에 실어 보냅니다. 실로봇과 동일한 인터페이스. 시뮬에서는 이 값이 PD action에 그대로 사용됨 — 실로봇 게인을 그대로 쓰면 됨.

**Q4. 카메라 해상도는 어디서 바꾸나?**
[teleimager/cam_config_server.yaml](teleimager/cam_config_server.yaml)의 `image_shape: [480, 640]` (auto_setup_env.sh가 자동 패치). 더 줄이면 ZMQ 대역폭/JPEG 인코딩 비용이 줄어듭니다.

**Q5. 다른 태스크로 바꾸면 USD가 어떻게 달라지나?**
- `Cylinder` → `RedBlock` → `Object`가 절차 cylinder 대신 RedBlock USD/cube
- `Stack-RgyBlock` → 빨간/초록/노란 블록 3개
- `Move-Cylinder-Wholebody` → 로봇이 다리 자유, USD가 wholebody 변형
실린더 → 적색 블록 같은 변경은 [tasks/common_scene/](tasks/common_scene/) 안의 다른 cfg 파일에서.

**Q6. DDS 메시지가 안 오면 어떻게 디버깅?**
1. `ROS_DOMAIN_ID=1` 양쪽 동일?
2. `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`?
3. 두 컨테이너 모두 `--network=host`?
4. `python -c "from unitree_sdk2py... ChannelFactoryInitialize(1); sub = ChannelSubscriber('rt/lowstate', LowState_); ..."` 로 직접 구독해서 콜백 호출 확인
5. 멀티캐스트 차단 환경이면 `cyclonedds.xml`로 unicast peers 설정

**Q7. 어떻게 하면 Sim이 더 빨라지나?**
- `--no_render --headless` (WebRTC, 카메라 텐서 모두 끔 → 200% 빨라질 수 있음)
- `--render_interval 4`로 렌더링만 듬성듬성
- `--solver_iterations 4` (정확도 ↓ 속도 ↑)

---

## 10. 한 페이지 요약 (치트시트)

```
1. AppLauncher → Kit boot (Omniverse Kit)
2. parse_env_cfg(task)
   └── PickPlaceG129DEX3JointEnvCfg
       └── Scene (warehouse + 6 tables + cylinder + G1 dex3 + 3 cameras)
           └── USD: g1_29dof_with_dex3_base_fix.usd, PackingTable.usd, warehouse.usd
3. gym.make(task, cfg) → ManagerBasedRLEnv
   └── PhysX 200Hz, decimation 2 → 100Hz 제어
4. run_isaacsim_server()  → ZMQ 55555/55556/55557 pub
5. create_dds_objects(args, env)
   └── ChannelFactoryInitialize(1)        # 도메인 1
       ├── G1RobotDDS:    rt/lowstate ↑   rt/lowcmd ↓
       ├── Dex3DDS:       rt/dex3/{l,r}/state ↑   .../cmd ↓
       ├── ResetPose:     rt/reset_pose/cmd ↓
       ├── SimState:      rt/sim_state ↑
       └── Rewards:       (publish only)
6. DDSActionProvider — rt/lowcmd → action tensor
7. RobotController.start()
   ├── DDSManager.start_publishing(...)   # publish thread @ 100Hz
   └── (subscribe는 SDK 콜백)
8. while: env.step(action)  +  sim_state_dds.write(...)  +  reset_pose 처리
```

행복한 디버깅 되시기를 — 막히면 위 §8 코드 지도부터 들여다 보세요.
