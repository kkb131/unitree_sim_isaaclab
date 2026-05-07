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

- [ ] H1-2 baseline 부팅 (`Isaac-PickPlace-Cylinder-H12-27dof-Inspire-Joint`)
- [ ] `rt/lowstate` publish 확인 (~94Hz)
- [ ] UR10e URDF 확보 (xacro → URDF)
- [ ] DG-5F URDF mesh 경로 점검 (`package://` → `file://`)
- [ ] UR10e + DG-5F 통합 xacro/URDF 생성 (UR10e tool0 ↔ DG-5F dg_base_link fixed joint)
- [ ] URDF → USD 변환 (`tools/convert_urdf.py --fix-base --merge-joints`)

## 2. Repo Reality (Plan 검증 결과)

- `robots/` 는 단일 `unitree.py` 파일 (per-robot dir 아님). `H12_CFG_WITH_INSPIRE_HAND` 처럼 ArticulationCfg block 추가 패턴.
- Single-hand DDS 레퍼런스 `inspire_dds.py` 는 `MotorCmds_/MotorStates_` (`unitree_go`) 사용. **본 plan은 가이드 따라 `HandCmd_/HandState_` (`unitree_hg`) 채택** — `motor_cmd` 가 variable-length sequence 임을 IDL 직접 검증 (`unitree_sdk2_python/.../_HandCmd_.py` line 25: `types.sequence['MotorCmd_']`).
- DG-5F URDF 20 revolute joint: `rj_dg_{1..5}_{1..4}` (5 fingers × 4). 7 fixed (`base`, `palm`, `_tip` × 5).
- URDF→USD: `tools/convert_urdf.py` 이미 존재. fallback `IsaacLab/scripts/tools/convert_urdf.py`.

## 3. H1-2 Baseline Boot Test (예정)

```bash
source /workspace/isaaclab/datasets/unitree_sim_isaaclab/activate_env.sh
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

결과: _TBD_

## 4. UR10e URDF 확보 (예정)

```bash
source /opt/ros/jazzy/setup.bash
xacro /opt/ros/jazzy/share/ur_description/urdf/ur.urdf.xacro \
  name:=ur10e ur_type:=ur10e \
  > /workspace/isaaclab/datasets/unitree_sim_isaaclab/assets/robots/ur10e-dg5f-urdf/ur10e.urdf
```

mesh `package://ur_description/...` 경로 처리: USD 변환 시 `OMNI_USD_RESOLVER_MDL_BUILTIN_*` 환경변수 또는 `package://` → `file://` sed 치환.

결과: _TBD_

## 5. DG-5F URDF mesh 경로 (예정)

```bash
grep -oE 'filename="[^"]+"' /workspace/isaaclab/datasets/teleop_system/models/dg5f/dg5f_right.urdf | sort -u
```

`package://` 경로면 mesh 디렉토리 복사 후 sed 치환.

결과: _TBD_

## 6. 통합 xacro 작성 (예정)

```xml
<!-- ur10e_with_dg5f.urdf.xacro -->
<robot name="ur10e_with_dg5f" xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:include filename="$(find ur_description)/urdf/ur.urdf.xacro"/>
  <xacro:ur_robot ur_type="ur10e" prefix=""/>

  <!-- include dg5f -->
  <xacro:include filename="dg5f_right.xacro"/>

  <!-- mount: UR10e tool0 ↔ DG-5F dg_base_link -->
  <joint name="ur10e_to_dg5f_mount" type="fixed">
    <parent link="tool0"/>
    <child link="dg_base_link"/>
    <origin xyz="0 0 0" rpy="0 0 0"/>
  </joint>
</robot>
```

마운트 RPY/XYZ 는 일단 identity, Day 5 시각 확인 후 보정.

결과: _TBD_

## 7. URDF → USD 변환 (예정)

```bash
cd /workspace/isaaclab/datasets/unitree_sim_isaaclab
python tools/convert_urdf.py \
  assets/robots/ur10e-dg5f-urdf/ur10e_with_dg5f.urdf \
  assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd \
  --fix-base --merge-joints \
  --joint-stiffness 100.0 --joint-damping 2.0
```

Fallback 1: `/workspace/isaaclab/datasets/IsaacLab/scripts/tools/convert_urdf.py` 직접 호출
Fallback 2: Isaac Sim GUI URDF importer extension

결과: _TBD_

## 8. Day 2 진입 가능 여부

위 1-7 모두 OK 시 Day 2 (robots/unitree.py + Reach task) 진입.

블록되는 사항: _TBD_
