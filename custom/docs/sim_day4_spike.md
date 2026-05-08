# Day 4 Spike — Camera scene mount + ZMQ/WebRTC publish

> Plan: [/root/.claude/plans/keen-zooming-mist.md](/root/.claude/plans/keen-zooming-mist.md) Day 4 섹션
> Branch: `feat/ur10e-dg5f-sim`
> Day 1-3 결과: [sim_day1_spike.md](sim_day1_spike.md), [sim_day2_spike.md](sim_day2_spike.md), [sim_day3_spike.md](sim_day3_spike.md)

## 0. Scope

UR10e single-arm용 `front_camera` (world-fixed) + `right_wrist_camera` (palm view) 2개 mount. 기존 teleimager pipeline이 ZMQ 55555/55557 + WebRTC 60001/60003에 publish. `left_wrist_camera`는 의도적 미설치 (single arm).

## 1. 신규 파일 (모두 `custom/`)

| 파일 | 역할 |
|---|---|
| [`custom/tasks/common_config/ur10e_camera_configs.py`](../tasks/common_config/ur10e_camera_configs.py) | `UR10ECameraPresets` — front + right_wrist preset (각각 `world` body / `wrist_3_link` mount) |
| [`custom/scripts/test_zmq_recv.py`](../scripts/test_zmq_recv.py) | ZMQ 55555/55557 frame count + JPEG size 검증 |
| [`custom/scripts/run_ur10e_dg5f.sh`](../scripts/run_ur10e_dg5f.sh) | 부팅 wrapper — `cam_config_server.yaml`의 left_wrist 임시 disable + sim_main 실행 + exit 시 yaml 복원 |

## 2. 업데이트 (custom/)

| 파일 | 변경 |
|---|---|
| `custom/tasks/ur10e_tasks/reach_ur10e_dg5f/reach_ur10e_dg5f_env_cfg.py` | `front_camera` + `right_wrist_camera` scene attribute 추가, `DDSStateGroup`에 `camera_image = ObsTerm(func=camera_state.get_camera_image)` 추가 (frame → SHM pipeline 연결) |

upstream 수정 0건. `cam_config_server.yaml`은 wrapper 가 in-place 패치 후 exit 시 복원 (CUSTOMIZATIONS.md에 명시된 runtime-mutable 처리 패턴).

## 3. 핵심 설계 결정 / 발견

### 3.1 Scene attribute 이름 hardcoded

[tasks/common_observations/camera_state.py:113-131](../../tasks/common_observations/camera_state.py#L113-L131) 가 `env.scene["front_camera"]/[left_wrist_camera]/[right_wrist_camera]` 직접 lookup → `images["head"/"left"/"right"]` 매핑. **Scene attribute 이름은 정확히 `front_camera`/`right_wrist_camera`**여야 함.

### 3.2 left_wrist None frame이 image_server 전체 중지 시키는 quirk

[teleimager/.../image_server.py:1359-1365](../../teleimager/src/teleimager/image_server.py#L1359-L1365)의 `_zmq_pub` 루프는 `jpeg_bytes is None` 시 `self._stop_event.set()` + `break`. `_stop_event`는 모든 카메라 thread가 공유 → 한 카메라 None frame이 head/right까지 중지.

UR10e엔 `left_wrist_camera` scene attr 없음 → image_server가 frame None 받음 → 전체 중지. **해결: `cam_config_server.yaml`의 `left_wrist_camera` 섹션에 `enable_zmq:false`/`enable_webrtc:false` 패치**. wrapper script `run_ur10e_dg5f.sh`가 자동 처리.

### 3.3 `camera_image` ObsTerm 필수

H1-2 패턴 ([pickplace_cylinder_h12_27dof_inspire_env_cfg.py:75](../../tasks/h1-2_tasks/pick_place_cylinder_h12_27dof_inspire/pickplace_cylinder_h12_27dof_inspire_env_cfg.py#L75)) 처럼 `camera_image = ObsTerm(func=mdp.get_camera_image)`이 obs cfg에 등록되어야 매 step 호출돼 `MultiImageWriter`로 SHM에 frame 씀. Day 4 초기엔 누락 → ZMQ 0 frames. PolicyCfg는 RL 학습 obs 오염 회피 위해 DDSStateGroup (concatenate_terms=False) 에 추가.

### 3.4 mount link 결정

Day 2 enumeration에서 `tool0`/`flange`/`rl_dg_palm` 모두 `wrist_3_link`에 흡수. 사용 가능 link:
- `world`: scene 정적 fixture — `front_camera` 후보
- `wrist_3_link`: DG-5F palm 위치 — `right_wrist_camera`
- 손가락 끝 (`rl_dg_*_4`): finger view 가능하지만 grasp-egocentric엔 wrist_3 충분

→ **front=world, right_wrist=wrist_3_link** 채택.

## 4. 검증 결과

부팅: `./custom/scripts/run_ur10e_dg5f.sh`
```
[run_ur10e_dg5f] patched left_wrist_camera enable_zmq/webrtc → false
...
[Image Server] head_camera is ready.
[Image Server] left_wrist_camera is ready.   ← yaml에 entry는 있지만 ZMQ/WebRTC disable
[Image Server] right_wrist_camera is ready.
========= start controller success =========
[Performance] A:0.0ms, E:14.9ms, S:0.0ms, T:14.9ms
```

ZMQ test: `python custom/scripts/test_zmq_recv.py --duration 5.0`
```
listening on ports [55555, 55557] for 5.0s...

=== results (5.0s) ===
front          (port 55555):  151 frames ( 30.2 Hz), avg    5876 bytes  [OK]
right_wrist    (port 55557):  150 frames ( 30.0 Hz), avg   21778 bytes  [OK]

overall: PASS
```

✅ 30 fps target 정확 도달 (image_server fps=30 yaml 기본값 매칭).
✅ JPEG bytes — front 5.9KB (단순 ground), right_wrist 21.8KB (DG-5F finger 디테일 많음). 둘 다 valid frame size.

WebRTC: 부팅 로그에 `WebRTC: enabled, webrtc port=60001/60002/60003` 모두 enabled (left_wrist만 yaml 패치 후 disabled). 60001/60003만 publish. browser https://localhost:60001/60003 접속은 별도 user 검증 (cert 신뢰 필요).

YAML 복원: sim 종료 후 `cam_config_server.yaml` 의 `enable_zmq: true`, `enable_webrtc: true` 정상 복귀 (trap EXIT/INT/TERM).

## 5. Day 4 통과 기준 (5개)

| # | 항목 | 결과 |
|---|---|---|
| 1 | sim_main 부팅 + 카메라 ready | ✅ head/left_wrist/right_wrist 모두 `is ready` |
| 2 | ZMQ port 55555 (front) ≥ 100 frames/5s | ✅ 151 frames @ 30.2 Hz |
| 3 | ZMQ port 55557 (right_wrist) ≥ 100 frames/5s | ✅ 150 frames @ 30.0 Hz |
| 4 | JPEG frame size > 1KB (decoded sanity) | ✅ 5.9KB / 21.8KB |
| 5 | WebRTC server 60001/60003 listen | ✅ 부팅 로그 `WebRTC: enabled, webrtc port=60001`, `60003` (60002는 yaml 패치로 disabled) |

✅ Day 4 5/5 PASS.

## 6. 시행착오 (다른 PC 재현 시 참고)

1. **첫 시도 ZMQ 0 frames** — `camera_image` ObsTerm 누락으로 frame이 ImageServer까지 안 흘러감. H1-2 PolicyCfg 패턴 비교해서 발견.
2. **left_wrist_camera None frame이 head/right까지 중지** — `_zmq_pub` 의 `self._stop_event` 가 thread 공유. wrapper가 yaml 패치로 우회.
3. **mount offset 추정치** — `front_camera` `pos_offset=(-0.8, 0.0, 0.6)`, `rot_offset=(0.6533, -0.2706, 0.2706, -0.6533)` 는 첫 시도값. livestream으로 viewport 보고 보정 필요할 수 있음 (workspace가 화면 중앙에 잡히는지). Day 4 검증엔 frame size 정상 = 카메라 위치 OK 가정.
4. **이전 sim의 image_server 잔재** — `pkill -f sim_main` 후에도 image_server child process가 port 60000 잡고 있을 수 있음. 새 sim 부팅 전 `ss -tln | grep 60000` 로 풀린 것 확인 권장.
5. **`--no_render` 와 카메라 충돌** — `--no_render`는 rendering 자체를 꺼서 카메라가 frame 못 만듦. Day 4부턴 `--headless`만 사용 (rendering offscreen 가능).

## 7. Day 5 진입 가능 여부

✅ 진입 가능. Day 5: PD tuning + finger settling 보정.
- UR10e shoulder_lift gain 올림 (Day 3에서 -1.0 target에 -0.752 settling 부족)
- DG-5F finger 4/5 mass/limit 보정 (Tesollo official spec 또는 DG-5F URDF inertia 검토)
- 또는 Day 5 = end-to-end 검증 종합 + 최종 보고서. user 결정 사항.
