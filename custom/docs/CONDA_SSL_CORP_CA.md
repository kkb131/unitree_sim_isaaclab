# CONDA SSL 트러블슈팅 — 사내 Root CA 호환 가이드

사내망 PC(특히 MITM proxy 환경)에서 `auto_setup_env.sh` 실행 시 `conda create` 가 SSL 에러로 실패할 때 적용하는 우회 가이드입니다.

## 1. 증상

```
CondaSSLError: ...
SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
 Basic Constraints of CA cert not marked critical (_ssl.c:1032)')
```

발생 조건:
- 사내 MITM proxy 환경에서 사내 root CA 인증서를 trust store에 추가한 상태
- Python ≥ 3.10 (특히 3.13) + miniforge3/Anaconda
- `conda config --set ssl_verify false`, `REQUESTS_CA_BUNDLE` 등 일반적인 설정으로 해결되지 않음
- 동일 머신에서 `curl`은 정상 동작 (비대칭)

## 2. 원인

사내 보안팀이 발급한 root CA 인증서가 **RFC 5280 §4.2.1.9 위반**:
`Basic Constraints` extension 에 `critical` flag 가 누락되어 있음.

| 클라이언트 | OpenSSL | 동작 |
|---|---|---|
| `curl` (대다수 OpenSSL 1.x 빌드) | 관대 | 통과 |
| Python 3.10+ (OpenSSL 3.x strict) | 엄격 | 거부 — `_ssl.c:1032` |

검증:

```bash
openssl x509 -in /usr/local/share/ca-certificates/<your-corp-ca>.crt -text -noout \
  | grep -A1 "Basic Constraints"
```

정상이라면 `X509v3 Basic Constraints: critical` 줄이 보여야 함. `critical` 단어가 없으면 사내 CA 결함이 확정.

## 3. 진단 절차

문제를 좁힐 때 사용한 명령들. 위에서 아래로 순서대로 실행하면 어디서 깨지는지 단계별로 잡힘.

```bash
# 3-1. raw miniforge3 python 직접 호출 (alias로 Isaac Sim python.sh 가로채는 함정 회피)
/root/miniforge3/bin/python -c "import sys; print('Python:', sys.version)"
/root/miniforge3/bin/python -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"

# 3-2. .bashrc 환경 누수 차단된 셸에서 conda 시도 — 같은 에러면 .bashrc 무관
bash --noprofile --norc -c '
  source /root/miniforge3/etc/profile.d/conda.sh
  conda create -y -n testenv python=3.11
'

# 3-3. curl vs python 비대칭 확인 (curl OK + python FAIL 이면 OpenSSL strict 차이 확정)
curl -v https://repo.anaconda.com/pkgs/main/linux-64/repodata.json 2>&1 | grep -E 'SSL|verify|subject'
/root/miniforge3/bin/python -c "
import urllib.request
urllib.request.urlopen('https://repo.anaconda.com/pkgs/main/linux-64/repodata.json', timeout=10)
"

# 3-4. conda verbose 로 정확한 실패 지점 확인
conda create -n testenv python=3.11 -vvv 2>&1 | grep -iE 'ssl|cert|verify' | head -30

# 3-5. urllib vs requests 분리 테스트 — 둘 다 깨지는지 확인
/root/miniforge3/bin/python <<'PY'
import urllib.request, requests
try:
    urllib.request.urlopen('https://repo.anaconda.com/pkgs/main/linux-64/repodata.json', timeout=10)
    print('urllib: OK')
except Exception as e: print('urllib FAIL:', e)
try:
    requests.get('https://conda.anaconda.org/conda-forge/noarch/repodata_shards.msgpack.zst', timeout=20)
    print('requests: OK')
except Exception as e: print('requests FAIL:', e)
PY
```

## 4. 해결책 — `sitecustomize.py` 자동 패치

Python은 시작 시 `site-packages` 어디든 `sitecustomize.py` 가 있으면 자동 import 합니다. 이를 이용해 conda 가 호출하는 모든 Python 프로세스에 일괄 적용.

### 4-1. 적용 위치

base interpreter 와 새로 만든 env 양쪽 모두 필요:

| 위치 | 용도 |
|---|---|
| `/root/miniforge3/lib/python3.13/site-packages/sitecustomize.py` | `conda create` 자체 |
| `/root/miniforge3/envs/<env_name>/lib/python<X.Y>/site-packages/sitecustomize.py` | env 내부 `pip install` 등 |

### 4-2. 파일 내용

```python
import ssl

# 1) urllib / http.client: 기본 HTTPS context를 unverified 로 강제
ssl._create_default_https_context = ssl._create_unverified_context

# 2) urllib3: InsecureRequestWarning 침묵
try:
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass

# 3) requests: Session.send 에서 verify=False 강제 (conda 내부 호출 경로)
try:
    import requests.sessions
    _orig_send = requests.sessions.Session.send

    def _send_unverified(self, request, **kwargs):
        kwargs['verify'] = False
        return _orig_send(self, request, **kwargs)

    requests.sessions.Session.send = _send_unverified
except Exception:
    pass
```

세 패치 모두 필요한 이유:
- conda 는 stdlib `urllib` 외에 `requests`/`urllib3` 도 사용. 한 곳만 패치하면 다른 경로에서 그대로 깨짐.
- `requests/urllib3` 미설치 환경(가벼운 env)에 그대로 복사돼도 `try/except` 가 ImportError 흡수.

### 4-3. 적용 명령

```bash
# base interpreter 의 정확한 site-packages 경로
PY_DIR=$(/root/miniforge3/bin/python -c "import site; print(site.getsitepackages()[0])")
echo "Target: $PY_DIR"

cat > "$PY_DIR/sitecustomize.py" <<'PYEOF'
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

try:
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass

try:
    import requests.sessions
    _orig_send = requests.sessions.Session.send

    def _send_unverified(self, request, **kwargs):
        kwargs['verify'] = False
        return _orig_send(self, request, **kwargs)

    requests.sessions.Session.send = _send_unverified
except Exception:
    pass
PYEOF
```

### 4-4. 검증

**중요**: 검증은 반드시 `/root/miniforge3/bin/python` 으로 직접 호출. shell alias (`alias python=/workspace/isaaclab/_isaac_sim/python.sh`) 가 있으면 false positive 가 나옴 — Isaac Sim 의 python 은 별도 OpenSSL 빌드라 strict 가 원래 비활성.

```bash
# 패치 로드 확인
/root/miniforge3/bin/python -c "
import ssl
print('https context is unverified:',
      ssl._create_default_https_context is ssl._create_unverified_context)
"
# 기대: True

# 네트워크 양쪽 검증
/root/miniforge3/bin/python <<'PY'
import urllib.request, requests
print('urllib:', urllib.request.urlopen('https://repo.anaconda.com/pkgs/main/linux-64/repodata.json', timeout=10).status)
print('requests:', requests.get('https://conda.anaconda.org/conda-forge/noarch/repodata_shards.msgpack.zst', timeout=20).status_code)
PY

# conda create 재시도
conda create -y -n testenv python=3.11
```

### 4-5. env 생성 후 후속 조치

`auto_setup_env.sh` 가 만든 env 안에서 `pip install` 도 SSL 을 거치므로 동일 파일 복사:

```bash
TARGET_ENV=unitree_sim_env  # auto_setup_env.sh 의 두 번째 인자
TARGET_PY=$(/root/miniforge3/envs/$TARGET_ENV/bin/python -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
cp /root/miniforge3/lib/python3.13/site-packages/sitecustomize.py \
   /root/miniforge3/envs/$TARGET_ENV/lib/$TARGET_PY/site-packages/
```

## 5. 보안 트레이드오프

- 위 패치는 **인증서 검증을 사실상 비활성화** 합니다 (`_create_unverified_context` + `verify=False`).
- 서명/만료/hostname/CA 체인 검증 모두 통과시키므로 **MITM 공격에 취약**.
- **사내망 한정, 신뢰 가능한 네트워크 가정** 하에서만 사용.
- **장기 해결책**: 사내 보안팀에 root CA 재발급 요청 — `basicConstraints = critical, CA:TRUE` 명시 (RFC 5280 §4.2.1.9 준수). 정상화되면 `sitecustomize.py` 삭제.

```
보안팀 요청 문구 예시:
  현재 사내 root CA 인증서가 RFC 5280 §4.2.1.9 위반(Basic Constraints
  extension에 critical flag 누락) 상태이며, OpenSSL 3.x 기반 Python 클라이언트
  (Python 3.10+, conda 등)에서 모두 거부됩니다.
  openssl req 발급 시 -extensions v3_ca 옵션으로 다음 항목 명시 부탁드립니다:
    basicConstraints = critical, CA:TRUE
```

## 6. 참고 — 시도했으나 실패한 정밀 패치

검증을 완전히 끄지 않고 `VERIFY_X509_STRICT` 플래그만 비활성화하는 더 안전한 방법을 시도했으나, conda 의존 라이브러리들의 다양한 SSLContext 생성 경로 때문에 일관 적용이 까다로움:

| 시도 | 결과 |
|---|---|
| `ssl.create_default_context` 만 monkeypatch | `urllib` OK, `requests/urllib3` 은 SSLContext 직접 생성하므로 실패 |
| `ssl._create_default_https_context` 추가 patch | `http.client` 캐시 참조 우회로 부분 성공 |
| `ssl.SSLContext` 서브클래스 교체 | stdlib `verify_mode.setter` 의 `super(SSLContext, SSLContext).__set__` 체인이 무한 재귀 |
| `ssl.SSLContext.__init__` 직접 부착 + 원본 호출 | Python 3.13 에서 `object.__init__(protocol)` TypeError |
| `__init__` 부착 (원본 호출 안 함) | 동작 가능. 보안 더 보존되지만 위 4번 채택안보다 덜 검증됨 |

→ 보안과 편의의 균형이 더 필요한 경우, 위 표의 마지막 행(`__init__` 부착) 접근 검토 가능.
