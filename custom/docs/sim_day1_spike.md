# Day 1 Spike — UR10e + DG-5F Sim Build

> 가이드: [vr_teleop/docs/SIM_UR10E_DG5F_BUILD_GUIDE.md](/workspace/isaaclab/datasets/vr_teleop/docs/SIM_UR10E_DG5F_BUILD_GUIDE.md)
> Plan: [/root/.claude/plans/keen-zooming-mist.md](/root/.claude/plans/keen-zooming-mist.md)
> Branch: `feat/ur10e-dg5f-sim`

## 0. Workspace Setup (사전 작업)

| 항목 | 결과 | 비고 |
|---|---|---|
| `unitree_sim_env` (Python 3.11.15) | ✅ | `/root/miniconda3/envs/unitree_sim_env/` |
| Isaac Sim / IsaacLab import | ✅ | IsaacLab at `/workspace/isaaclab/datasets/IsaacLab` |
| `unitree_sdk2py` import | ✅ | `/workspace/isaaclab/datasets/unitree_sdk2_python/` |
| `activate_env.sh` 수정 | ✅ | `/root/miniforge3/` → `/root/miniconda3/` (실제 conda 위치) |
| ROS 2 Jazzy + `ur_description` + `xacro` | ✅ | `apt install ros-jazzy-ur-description ros-jazzy-xacro` 완료. UR10e xacro: `/opt/ros/jazzy/share/ur_description/urdf/ur.urdf.xacro` |
| `feat/ur10e-dg5f-sim` git branch | ✅ | origin/main e3bcc34 base + activate_env.sh 수정 |
| 작업 디렉토리 skeleton | ✅ | `assets/robots/ur10e-dg5f-{urdf,usd}/`, `tasks/ur10e_tasks/reach_ur10e_dg5f/mdp/`, `docs/` |

## 1. §2.3 Checklist (가이드)

- [ ] H1-2 baseline 부팅 (`Isaac-PickPlace-Cylinder-H12-27dof-Inspire-Joint`) — 미실행 (Day 2 진입 전 또는 Day 5 검증 단계로 연기)
- [ ] `rt/lowstate` publish 확인 (~94Hz) — H1-2 부팅 시 함께
- [x] UR10e URDF 확보 (xacro → URDF, 297 lines, mesh 절대경로)
- [x] DG-5F URDF mesh 경로 점검 (`package://dg_description/meshes/` → `file:///workspace/isaaclab/datasets/teleop_system/models/dg5f/meshes/`)
- [x] UR10e + DG-5F 통합 URDF 생성 (UR10e tool0 ↔ DG-5F rl_dg_mount fixed joint, 41 link / 40 joint / **26 revolute**)
- [x] URDF → USD 변환 (IsaacLab `scripts/tools/convert_urdf.py`, `--merge-joints --fix-base`, output 18MB)

## 2. Repo Reality (Plan 검증 결과)

- `robots/` 는 단일 `unitree.py` 파일 (per-robot dir 아님). `H12_CFG_WITH_INSPIRE_HAND` 처럼 ArticulationCfg block 추가 패턴.
- Single-hand DDS 레퍼런스 `inspire_dds.py` 는 `MotorCmds_/MotorStates_` (`unitree_go`) 사용. **본 plan은 가이드 따라 `HandCmd_/HandState_` (`unitree_hg`) 채택** — `motor_cmd` 가 variable-length sequence 임을 IDL 직접 검증 (`unitree_sdk2_python/.../_HandCmd_.py` line 25: `types.sequence['MotorCmd_']`).
- DG-5F URDF 20 revolute joint: `rj_dg_{1..5}_{1..4}` (5 fingers × 4). 7 fixed (`base`, `palm`, `_tip` × 5).
- URDF→USD: `tools/convert_urdf.py` 이미 존재. fallback `IsaacLab/scripts/tools/convert_urdf.py`.

## 3. H1-2 Baseline Boot Test (미실행)

가이드 §5 Day 1 step 3의 baseline 검증은 livestream viewer 환경 + Isaac Sim 첫 부팅 (수 분) 필요해서 **Day 2 cfg 작성 후 함께 또는 Day 5 검증 단계로 연기**. URDF 작업이 deterministic blocker였으므로 그것을 우선 처리.

부팅 명령:

```bash
source /workspace/isaaclab/datasets/unitree_sim_isaaclab/custom/scripts/activate_env.sh
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
python sim_main.py \
  --task Isaac-PickPlace-Cylinder-H12-27dof-Inspire-Joint \
  --enable_inspire_dds --robot_type h1_2 \
  --device cuda:0 --enable_cameras \
  --livestream_type 2 --public_ip 127.0.0.1
```

DDS publish 검증:
```bash
python - <<'PY'
import time
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
ChannelFactoryInitialize(1)
counts = {"n": 0}
def cb(msg): counts["n"] += 1
sub = ChannelSubscriber("rt/lowstate", LowState_)
sub.Init(cb, 10)
time.sleep(3)
sub.Close()
print(f"received {counts['n']} msgs in 3s (expect ~280)")
PY
```

결과: 미실행 (Day 2 합류)

## 4-7. Asset 생성 (단일 build script로 통합) ✅

Upstream convention(`assets/`는 git 무시, `fetch_assets.sh`로 다운로드)에 맞춰 reproducible build script 작성:

```bash
source /workspace/isaaclab/datasets/unitree_sim_isaaclab/custom/scripts/activate_env.sh
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
./custom/tools/build_ur10e_dg5f_assets.sh
```

스크립트 4단계 (소스: [custom/tools/build_ur10e_dg5f_assets.sh](/workspace/isaaclab/datasets/unitree_sim_isaaclab/custom/tools/build_ur10e_dg5f_assets.sh)):

1. **UR10e URDF 생성** — `xacro ur.urdf.xacro name:=ur10e ur_type:=ur10e force_abs_paths:=true`. `force_abs_paths` 덕분에 mesh 절대경로(`file:///opt/ros/jazzy/share/ur_description/meshes/ur10e/...`)로 emit, sed 치환 불필요. 297 lines, 6 revolute joints (`shoulder_pan/lift, elbow, wrist_{1,2,3}`), mount 후보 link `tool0` (chain `wrist_3_link → flange → tool0`).

2. **DG-5F URDF sed-replace** — 원본 [dg5f_right.urdf](/workspace/isaaclab/datasets/teleop_system/models/dg5f/dg5f_right.urdf)는 `package://dg_description/meshes/...` 사용. 본 docker엔 ROS package 등록 안 됨 → `file:///workspace/isaaclab/datasets/teleop_system/models/dg5f/meshes/` 로 치환. 40+ mesh path 전수 검증, 빠진 파일 없음. URDF root link: **`rl_dg_mount`**.

3. **통합 URDF 머지** — [custom/tools/combine_ur10e_dg5f_urdfs.py](/workspace/isaaclab/datasets/unitree_sim_isaaclab/custom/tools/combine_ur10e_dg5f_urdfs.py) (Python `xml.etree.ElementTree`). xacro `<xacro:include>` 방식은 ur.urdf.xacro 의 `<robot>` 충돌 때문에 어려움 → 두 URDF의 `<link>`/`<joint>` element를 새 `<robot name="ur10e_with_dg5f">`에 직접 머지. mount: `tool0` (parent) ↔ `rl_dg_mount` (child) fixed joint, xyz/rpy=identity (Day 5 보정 예정). 결과: 41 link / 40 joint / **26 revolute** (UR10e 6 + DG-5F 20: `rj_dg_{1..5}_{1..4}`).

4. **URDF → USD 변환** — `unitree_sim_isaaclab/tools/convert_urdf.py`는 hardcoded path 라 unusable. **IsaacLab 표준 [scripts/tools/convert_urdf.py](/workspace/isaaclab/datasets/IsaacLab/scripts/tools/convert_urdf.py) 사용** (`--merge-joints --fix-base --headless`). 산출: `ur10e_with_dg5f.usd` (1.4KB main + 4 layered, 총 18MB).

⚠️ **`--merge-joints` 부작용**: Isaac Sim importer가 fixed joint로 연결된 link들을 머지함 — 변환 로그에서:
- `tool0`, `flange`, `rl_dg_mount`, `rl_dg_base`, `rl_dg_palm`, `rl_dg_{1..5}_tip` 등이 모두 다른 link로 흡수됨
- `tool0` → `flange` → `wrist_3_link`로 머지되는 chain 발생
- DG-5F의 `rl_dg_mount` → `tool0`로 흡수 (즉 wrist_3_link로 흡수)

영향 분석:
- ✅ 26 revolute joint articulation은 그대로 유지 (USD에 보존)
- ⚠️ Day 4 카메라 mount 시 `tool0` prim이 USD에 존재 안 할 수도 — 대안 link (`wrist_3_link`, `rl_dg_1_4` 등) 사용 필요 검토
- ⚠️ Day 2 cfg 작성 시 IsaacLab `Articulation.body_names`로 실제 USD link 이름 enumerate해서 reach task의 EE body 결정해야 함

`--merge-joints` 빼고 재변환할 옵션 — **Day 2 첫 부팅에서 link 이름 enumerate 후 결정**.

## 8. Day 2 진입 가능 여부

✅ 진입 가능. URDF/USD asset 확보 완료. Day 2 작업:
1. `robots/unitree.py` 에 `UR10E_WITH_DG5F_HAND` ArticulationCfg block 추가 (USD link 이름 enumerate 후 actuators/init_state 작성)
2. `tasks/common_config/robot_configs.py` 에 `UR10ERobotPresets.ur10e_dg5f()` 추가
3. `tasks/ur10e_tasks/reach_ur10e_dg5f/` 신규 + `Isaac-Reach-UR10e-DG5F-Joint` 등록
4. `sim_main.py` `--robot_type ur10e` 분기 추가
5. 부팅 검증 + 필요 시 USD 재변환 (`--merge-joints` 제거)

블록 사항: 없음. H1-2 baseline 검증은 Day 2 부팅 시 자연스럽게 환경 sanity 확인되므로 별도 step 불필요.
