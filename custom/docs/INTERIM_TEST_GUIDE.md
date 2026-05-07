# UR10e + DG-5F Sim — Interim Test Guide (Day 1 Reproduction)

> 본 가이드는 **다른 PC**에서 현재까지의 진척(Day 1 — UR10e+DG-5F 통합 URDF/USD 빌드)을 재현하고 검증하는 절차를 정리한 문서입니다.
> 진행 상태: Day 1 완료, Day 2(unitree.py cfg + Reach task 등록) 미진행. 즉 **sim_main 부팅 검증은 본 가이드 범위 밖**이며, 본 가이드는 빌드 파이프라인의 **재현 가능성**(reproducibility)에 집중합니다.
>
> 원천 가이드: [SIM_UR10E_DG5F_BUILD_GUIDE.md](/workspace/isaaclab/datasets/vr_teleop/docs/SIM_UR10E_DG5F_BUILD_GUIDE.md)
> Day 1 결과: [sim_day1_spike.md](sim_day1_spike.md)

---

## 1. Hardware / OS Prereq

| 항목 | 값 |
|---|---|
| OS | Ubuntu 24.04 (Noble Numbat) — Isaac Sim 5.1 공식 지원 |
| GPU | NVIDIA RTX 3080 Ti 이상 권장 (RTX 4090/5090 검증) |
| GPU Memory | 12GB 이상 |
| RAM | 32GB 이상 |
| Disk | 100GB 이상 (Isaac Sim ~30GB + IsaacLab + USD 캐시) |
| NVIDIA Driver | 535+ (Vulkan/CUDA 12.6+ 호환) |
| Docker | `--network=host` + `--gpus all` 필수 (DDS multicast + Vulkan) |

본 docker가 검증된 조합:
- AMD Ryzen 9 7950X3D, 64GB RAM
- NVIDIA RTX 4090 24GB (Driver 580.126.09)
- Ubuntu 24.04.3 LTS
- Vulkan + CUDA 정상

---

## 2. 사전 설치 항목 (System / Conda)

다음 항목이 모두 갖춰져 있다고 전제합니다. 빠진 게 있으면 그 항목부터 셋업 후 본 가이드 step 4로 진입하세요.

### 2.1 conda 환경 (`unitree_sim_env`)

`auto_setup_env.sh` (또는 `auto_setup_env_venv.sh`)로 셋업된 Python 3.11 conda env. Isaac Sim 5.1, IsaacLab 0.46.6, unitree_sdk2py가 import 가능해야 함.

**검증**:
```bash
source <repo>/custom/scripts/activate_env.sh
python -c "import isaacsim, isaaclab, unitree_sdk2py; print('OK')"
```

⚠️ `custom/scripts/activate_env.sh` 가 conda 설치 위치를 가리키므로, **머신에 conda가 `/root/miniconda3/`가 아닌 다른 위치**(예: `/root/miniforge3/`, `/opt/conda/`)에 있으면 `source ... conda.sh` 라인 수정 필요. 본 docker는 `miniconda3`로 patch된 상태.

### 2.2 IsaacLab 0.46.6

repo clone 위치는 환경변수 `ISAACLAB_ROOT`로 override 가능. 기본값: `/workspace/isaaclab/datasets/IsaacLab`.

**검증**:
```bash
ls "$ISAACLAB_ROOT/scripts/tools/convert_urdf.py"   # Day 1 step 4 의존
```

### 2.3 ROS 2 Jazzy + UR description + xacro

```bash
sudo apt update
sudo apt install -y ros-jazzy-ur-description ros-jazzy-xacro
```

**검증**:
```bash
ls /opt/ros/jazzy/share/ur_description/urdf/ur.urdf.xacro    # exists
xacro --help | head -3                                       # works
ls /opt/ros/jazzy/share/ur_description/meshes/ur10e/         # collision/, visual/
```

### 2.4 DG-5F 소스 (URDF + meshes)

기본 경로: `/workspace/isaaclab/datasets/teleop_system/models/dg5f/`. 다르면 환경변수 `DG5F_SRC`로 override.

**검증**:
```bash
ls "$DG5F_SRC/dg5f_right.urdf"                              # 27 joint URDF
ls "$DG5F_SRC/meshes/dg5f_right/visual/"                    # *.dae
ls "$DG5F_SRC/meshes/dg5f_right/collision/"                 # *.STL
```

### 2.5 `unitree_sdk2_python` (CycloneDDS bindings)

기본 위치: `/workspace/isaaclab/datasets/unitree_sdk2_python/` — `pip install -e` 형태로 설치되어 있어야 함.

**검증** (Day 1 범위 내에선 import만 확인):
```bash
python -c "from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_, HandState_, LowState_; print('OK')"
```

---

## 3. Repo Clone + Branch Checkout

```bash
cd /workspace/isaaclab/datasets   # 또는 원하는 위치
git clone <fork URL> unitree_sim_isaaclab
cd unitree_sim_isaaclab
git checkout feat/ur10e-dg5f-sim
git log --oneline -5
```

기대 commit (Day 1 시점):
```
ce01ab8 chore(repo): consolidate non-upstream files under custom/
1e58dab feat(assets): Day 1 — UR10e+DG-5F integrated URDF/USD build pipeline
e37fec9 chore(setup): fix conda path and seed Day 1 spike doc for UR10e+DG-5F
```

(이 가이드 자체를 추가한 commit이 위에 더 있을 수 있음.)

---

## 4. 빌드 실행 (Day 1 산출물 재현)

```bash
source custom/scripts/activate_env.sh
cd <repo root>
./custom/tools/build_ur10e_dg5f_assets.sh
```

스크립트 동작 (예상 소요: 5–10분, 대부분 step 4 USD 변환):
- **[1/4]** UR10e xacro → `assets/robots/ur10e-dg5f-urdf/ur10e.urdf` (~1초)
- **[2/4]** DG-5F URDF mesh path sed → `assets/robots/ur10e-dg5f-urdf/dg5f_right.urdf` (~즉시)
- **[3/4]** 통합 URDF 머지 → `assets/robots/ur10e-dg5f-urdf/ur10e_with_dg5f.urdf` (~즉시)
- **[4/4]** Isaac Sim 부팅 + URDF→USD 변환 → `assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd` (5–10분, Isaac Sim 첫 부팅 시 더 오래)

성공 종료 시 마지막 줄: `[done] USD: .../ur10e_with_dg5f.usd`.

### 환경변수 override 예시
```bash
DG5F_SRC=/path/to/your/dg5f \
ISAACLAB_ROOT=/path/to/your/IsaacLab \
./custom/tools/build_ur10e_dg5f_assets.sh
```

### Smoke test (USD 변환 skip — URDF만 검증)
USD 변환은 5–10분 걸리므로 path/환경 sanity 만 빠르게 확인하려면 `SKIP_USD=1`:
```bash
SKIP_USD=1 ./custom/tools/build_ur10e_dg5f_assets.sh
```
→ §5.1 와 §5.2 만 통과 가능 (§5.3 USD 산출은 SKIP_USD=0 으로 다시 빌드 필요).

---

## 5. 검증 항목

### 5.1 통합 URDF: 26 revolute joint 카운트

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
t = ET.parse("assets/robots/ur10e-dg5f-urdf/ur10e_with_dg5f.urdf")
joints = t.getroot().findall("joint")
revs = [j.get("name") for j in joints if j.get("type") == "revolute"]
ur_revs = [n for n in revs if any(k in n for k in ("shoulder","elbow","wrist"))]
dg_revs = [n for n in revs if n.startswith("rj_dg_")]
print(f"total joints: {len(joints)}")
print(f"revolute total: {len(revs)}")
print(f"  UR10e arm: {len(ur_revs)} = {ur_revs}")
print(f"  DG-5F: {len(dg_revs)} = {dg_revs}")
mount = [j for j in joints if j.get("name") == "ur10e_to_dg5f_mount"]
assert mount, "missing mount joint"
print(f"mount joint: parent={mount[0].find('parent').get('link')} child={mount[0].find('child').get('link')}")
assert len(revs) == 26, "expected 26 revolute joints"
assert len(ur_revs) == 6 and len(dg_revs) == 20
print("PASS")
PY
```

기대 출력:
```
total joints: 40
revolute total: 26
  UR10e arm: 6 = ['shoulder_pan_joint','shoulder_lift_joint','elbow_joint','wrist_1_joint','wrist_2_joint','wrist_3_joint']
  DG-5F: 20 = ['rj_dg_1_1','rj_dg_1_2',...,'rj_dg_5_4']
mount joint: parent=tool0 child=rl_dg_mount
PASS
```

### 5.2 Mesh path 무결성 (UR10e + DG-5F)

```bash
python3 - <<'PY'
import re, os
text = open("assets/robots/ur10e-dg5f-urdf/ur10e_with_dg5f.urdf").read()
paths = sorted(set(re.findall(r'filename="(file://[^"]+)"', text)))
missing = [p for p in paths if not os.path.exists(p[7:])]   # strip 'file://'
print(f"unique mesh refs: {len(paths)}")
print(f"missing: {len(missing)}")
for p in missing[:5]:
    print(f"  {p}")
assert not missing, "some mesh files missing"
print("PASS")
PY
```

기대: `missing: 0` + `PASS`. 만약 누락 발견되면 `DG5F_SRC` 또는 `ros-jazzy-ur-description` 설치를 재확인하세요.

### 5.3 USD 파일 산출 확인

```bash
ls -lh assets/robots/ur10e-dg5f-usd/
ls -lh assets/robots/ur10e-dg5f-usd/configuration/
file assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd
```

기대:
- `ur10e_with_dg5f.usd` (~1.4KB, USD crate 0.9.0)
- `configuration/ur10e_with_dg5f_base.usd` (~18MB, mesh 포함)
- `configuration/ur10e_with_dg5f_{physics,robot,sensor}.usd`

### 5.4 (선택) USD articulation 점검

이 검증은 Isaac Sim 부팅(수십 초) 필요. Day 2 전 sanity check 용도라 필수 아님.

```bash
python <<'PY'
from isaaclab.app import AppLauncher
from argparse import Namespace
app = AppLauncher(Namespace(headless=True, livestream=0)).app
from pxr import Usd, UsdPhysics
stage = Usd.Stage.Open("assets/robots/ur10e-dg5f-usd/ur10e_with_dg5f.usd")
revs = [p.GetPath().pathString for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)]
arts = [p.GetPath().pathString for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
print(f"articulation roots: {arts}")
print(f"revolute joints: {len(revs)}")
assert len(revs) == 26
print("PASS")
app.close()
PY
```

기대: `articulation roots: ['/...']`, `revolute joints: 26`, `PASS`.

---

## 6. Known Caveats (Day 1 시점에서 알고 있는 것)

### 6.1 `--merge-joints` 부작용

build script는 `--merge-joints --fix-base`로 호출. Isaac Sim importer가 fixed joint로 연결된 link들을 흡수:

| 흡수 전 | 흡수 결과 (대상 link) |
|---|---|
| `tool0`, `flange`, `rl_dg_mount`, `rl_dg_base`, `rl_dg_palm` | `wrist_3_link` |
| `rl_dg_{1..5}_tip` | `rl_dg_{1..5}_4` |

영향:
- ✅ 26 revolute joint articulation은 보존 (DDS PD 제어 OK)
- ⚠️ Day 4 카메라 mount 시 USD에서 `tool0` prim이 안 보일 수 있음 → 대안 mount link (`wrist_3_link`, `rl_dg_1_4`) 사용 검토
- ⚠️ Day 2 cfg 작성 시 `Articulation.body_names`로 USD 실 link 이름 enumerate 필요. 일치 안 하면 `--merge-joints` 빼고 재변환 필요

### 6.2 Mount RPY/XYZ 미보정

build script는 `tool0` ↔ `rl_dg_mount` 사이를 `xyz="0 0 0" rpy="0 0 0"` (identity)로 결합. 실제 DG-5F 마운트 어댑터의 기하학적 오프셋은 **Day 5 PD tuning 단계에서 시각 확인 후 보정** 예정. Day 1 산출물은 articulation 동작 검증 목적 한정.

### 6.3 conda 위치 의존

[`custom/scripts/activate_env.sh`](../scripts/activate_env.sh) line 8이 `source /root/miniconda3/etc/profile.d/conda.sh` (본 docker 한정 fix). upstream/main은 `/root/miniforge3/`을 가리킴. 환경 매번 확인 필요.

### 6.4 `assets/`는 git 추적 안 됨

upstream `.gitignore` line 122-124가 `assets/` 전체 ignore. build script 산출물(URDF + USD)는 매 환경에서 build script 재실행해 생성해야 함. 본 가이드 §4 흐름 그대로.

---

## 7. Troubleshooting

| 증상 | 원인 / 해결 |
|---|---|
| `xacro: command not found` | `ros-jazzy-xacro` 미설치. `sudo apt install ros-jazzy-xacro` |
| `dg5f_right.urdf` not found | `DG5F_SRC` 환경변수 잘못 됨. §2.4 검증 |
| `convert_urdf.py: file does not exist` | `ISAACLAB_ROOT` 잘못됨. `ls $ISAACLAB_ROOT/scripts/tools/convert_urdf.py` 확인 |
| `ImportError: No module named 'isaacsim'` | conda env 미활성화. `source custom/scripts/activate_env.sh` 후 재실행 |
| `CondaError: Run 'conda init'` | conda 위치가 script가 가정한 곳과 다름. activate_env.sh의 `source ...conda.sh` 라인 수정 |
| Isaac Sim 부팅이 EULA prompt에서 멈춤 | env vars `OMNI_KIT_ACCEPT_EULA=Y`, `PRIVACY_CONSENT=Y` 설정 (activate_env.sh 가 처리하지만 별도 shell에서 실행 시 누락 가능) |
| Vulkan 초기화 실패 | NVIDIA driver/Vulkan loader 확인 (`vulkaninfo --summary`). docker 환경이면 `--gpus all` 필요 |
| Mesh 파일 누락 (`MISSING: file://...`) | DG5F_SRC 또는 ur_description 일부 파일 누락. §5.2 출력 확인 후 누락된 디렉토리 재셋업 |

---

## 8. 결과 보고 형식

검증 통과 시 다음 형태로 보고:

```
[Day 1 REPRODUCTION OK]
Machine: <hostname>, GPU: <model>, Driver: <ver>
Repo HEAD: <git rev-parse HEAD>

§5.1 26 revolute joint: ✅
§5.2 mesh integrity:    ✅
§5.3 USD output size:   ✅ (base.usd <size MB>)
§5.4 articulation:      ✅ / SKIPPED

Build elapsed: <minutes>
Issues encountered: <list or "none">
```

이 결과를 본 docker(xr_teleop dev PC)로 회신 → Day 2 진입 결정.

---

## 9. Day 2 검증 절차 (Reach task standalone boot)

Day 2에서는 `UR10e+DG-5F` ArticulationCfg + Reach task가 모두 `custom/` 하위에 들어왔고 `sim_main.py`/DDS는 안 건드림. 검증은 standalone boot script로:

```bash
source custom/scripts/activate_env.sh
python -u custom/scripts/test_ur10e_dg5f_boot.py --headless
# 또는 viewport:
# python -u custom/scripts/test_ur10e_dg5f_boot.py --livestream 2 --public_ip 127.0.0.1
```

`-u` (unbuffered) 권장 — Isaac Sim warning이 stdout buffering을 흔들어 우리 print가 먹힐 수 있음.

### 통과 기준

스크립트가 자체 assert로 다음을 검증 + 마지막에 `PASS — 50 steps executed without crash` 출력:

| # | 항목 | 기대값 |
|---|---|---|
| 1 | `joint_names` 길이 | 26 |
| 2 | UR10e arm joint 개수 (`shoulder/elbow/wrist` 매칭) | 6 |
| 3 | DG-5F joint 개수 (`rj_dg_*` prefix) | 20 |
| 4 | `wrist_3_link` ∈ `body_names` | True |
| 5 | 50 zero-action step 무사고 | "PASS" 출력 |

기대 `body_names` 27개 (참고):
```
world, shoulder_link, upper_arm_link, forearm_link, wrist_1_link, wrist_2_link, wrist_3_link,
rl_dg_{1..5}_1, rl_dg_{1..5}_2, rl_dg_{1..5}_3, rl_dg_{1..5}_4
```

`tool0`/`flange`/`rl_dg_mount`/`rl_dg_palm`/`rl_dg_*_tip` 은 USD 빌드 시 `--merge-joints` 로 인해 흡수돼 **없음**. `wrist_3_link`이 EE body 역할.

기대 `joint_names` 등장 순서 (Day 3 DDS index 매핑 참조):
```
[0..5]   shoulder_pan/lift, elbow, wrist_{1,2,3}
[6..10]  rj_dg_{1..5}_1   ← finger * 첫 마디
[11..15] rj_dg_{1..5}_2
[16..20] rj_dg_{1..5}_3
[21..25] rj_dg_{1..5}_4
```

### 실패 시 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `ModuleNotFoundError: No module named 'custom'` | `__file__` 기반 sys.path 부트스트랩이 작동 안 한 환경. `cd <repo root> && PYTHONPATH=. python -u custom/scripts/test_ur10e_dg5f_boot.py --headless` |
| `AttributeError: module 'mdp' has no attribute 'position_command_error'` | mdp/__init__.py 에서 `isaaclab_tasks.manager_based.manipulation.reach.mdp` re-export 누락 — 이미 패치되어있어야 함 |
| `joint_names != 26` | USD가 다른 빌드 (e.g., --merge-joints 빠진) → 본 가이드 §4 build script 재실행 |
| `wrist_3_link not in body_names` | --merge-joints 가 다르게 작용했거나 USD root 다름. body_names 출력 보고 `reach_ur10e_dg5f_env_cfg.py` 의 `DEFAULT_EE_BODY` 후보 (`tool0`, `rl_dg_palm` 등) 로 변경 |
| `print` 출력 안 보임 | stdout buffering — 반드시 `python -u` 사용 |
| Isaac Sim 부팅 5분 이상 hang | 첫 부팅은 USD 캐시 만들기 때문에 시간 소요 가능. 두 번째부터는 30초 이내 |

## 10. Next Steps (Day 3 미진행)

Day 3 부터는 DDS round-trip 작업:
- `dds/dg5f_dds.py` (rt/dg5f/{state,cmd}) 신규
- `dds/dds_create.py` + `action_provider/action_provider_dds.py` 수정 (`--robot_type ur10e` + `--enable_dg5f_dds` 분기)
- `sim_main.py` argparse 확장
- 검증: `rt/lowstate` (motor[0:6]) + `rt/dg5f/state` (motor[0:20]) publish 확인

Day 3 진입 시 본 가이드에 §B. Day 3 검증 섹션이 추가될 예정.
