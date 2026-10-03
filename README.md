# AI Auto Trader — Toss Securities

개인용 토스증권 자동매매 플랫폼의 초기 구현입니다.

## 구조

- `frontend/` — GitHub Pages용 관제 대시보드
- `backend/` — FastAPI 기반 트레이딩 서버
- `backend/app/toss.py` — 토스증권 Open API 클라이언트
- `backend/app/strategy.py` — 전략 엔진
- `backend/app/risk.py` — 주문 전 안전장치
- `.github/workflows/pages.yml` — GitHub Pages 배포

## 현재 안전 상태

기본값은 **PAPER 모드**이며 실제 주문을 보내지 않습니다.
실전 주문은 서버의 `TRADING_MODE=live`와 별도의 안전장치가 모두 명시적으로 활성화된 경우에만 허용하도록 설계합니다.

API Secret은 절대 저장소에 커밋하지 마세요.

## 필요한 환경변수

```env
TOSS_CLIENT_ID=
TOSS_CLIENT_SECRET=
TOSS_ACCOUNT_SEQ=
TRADING_MODE=paper
ALLOWED_ORIGINS=https://heh-heh.github.io
MAX_ORDER_KRW=100000
MAX_DAILY_LOSS_KRW=50000
```

토스증권 Open API는 OAuth 2.0 Client Credentials를 사용하며 계좌/주문 API에는 accountSeq가 필요합니다.

## 개발 순서

1. Paper mode에서 시세/계좌 연동
2. 전략 및 백테스트
3. 주문 시뮬레이터
4. 모의/검증
5. 별도 서버에 배포
6. 마지막에만 live trading 활성화

> GitHub Pages는 관제 UI만 담당합니다. API Secret과 실제 주문 실행은 백엔드 서버에서 담당합니다.


<!-- deployment note -->

## Termux 휴대폰 서버

휴대폰에서 Termux를 서버로 사용할 수 있습니다.

### 최초 1회 설치

```bash
git clone https://github.com/heh-heh/ai-auto-trad.git
cd ai-auto-trad
bash termux_setup.sh
```

설치 후 `backend/.env`에 Toss 환경변수를 휴대폰에서 직접 설정합니다. API Secret은 GitHub에 올리지 않습니다.

### 서버 실행

```bash
cd ai-auto-trad
bash termux_run.sh
```

서버 확인:

```bash
curl http://127.0.0.1:8000/health
```

브라우저에서 확인:

```
http://127.0.0.1:8000/docs
```

서버 종료:

```bash
bash termux_stop.sh
```

기본 설정은 PAPER 모드이며 실제 주문은 비활성화되어 있습니다.

> 참고: 휴대폰에서 서버를 실행하는 것과 GitHub Pages가 인터넷을 통해 휴대폰 서버에 접근할 수 있게 만드는 것은 별개의 문제입니다. 외부 접근이 필요하면 다음 단계에서 터널/네트워크 구성을 추가합니다.


## 휴대폰 Termux 서버 (간단 버전)

Termux에서는 FastAPI 백엔드와 별도로 `termux_server/`를 사용합니다. Python 표준 라이브러리만 사용하므로 Pydantic/Rust 빌드가 필요 없습니다.

최초 1회:
```bash
git pull
bash termux_setup.sh
```

서버 실행:
```bash
bash termux_start.sh
```

백그라운드 실행:
```bash
bash termux_background.sh
```

상태 확인:
```bash
curl http://127.0.0.1:8000/health
```

Toss 현재가:
```bash
curl http://127.0.0.1:8000/api/price/005930
```

서버 로그:
```bash
tail -f logs/server.log
```

종료:
```bash
bash termux_stop.sh
```

Termux 서버의 기본 모드는 PAPER이며 실제 주문 API는 별도로 활성화하지 않습니다.

## Termux + GitHub Pages 운영

현재 배포 구조는 GitHub Pages 관제 화면 → HTTPS Tunnel → Android Termux 서버 → Toss Open API 입니다.

Termux 서버는 PAPER 모드가 기본이며, 현재 자동매매 엔진도 PAPER 모드에서만 주문을 생성합니다. 실제 주문은 아직 활성화하지 않습니다.

### 서버

bash termux_background.sh
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/toss/status
curl http://127.0.0.1:8000/api/price/005930

### GitHub Pages 외부 연결

휴대폰의 localhost를 GitHub Pages에서 사용하려면 HTTPS Tunnel이 필요합니다. Cloudflare Tunnel은 로컬 HTTP 서비스를 공개 HTTPS hostname으로 연결할 수 있고 Quick Tunnel은 개발용 임시 trycloudflare.com 주소를 제공합니다.

Termux:

pkg install cloudflared -y
bash termux_tunnel.sh

백그라운드:

bash termux_tunnel_background.sh
tail -f logs/tunnel.log

로그에 표시되는 https://xxxxx.trycloudflare.com 주소를 GitHub Pages의 서버 연결 → API 서버 주소에 입력합니다.

관제 토큰은 다음으로 확인합니다.

cat termux_server/.control_token

그 값을 GitHub Pages의 관제 토큰에 입력하고 연결 저장을 누릅니다.

Quick Tunnel은 재시작하면 주소가 바뀔 수 있습니다. 장기 운영에서는 본인 도메인을 Cloudflare에 연결한 named tunnel을 사용하는 편이 적합합니다.

### 대시보드 기능

- 현재가 / 캔들 / SMA5 / SMA20 / RSI14
- 실시간 호가 조회
- Paper 평가금 / 현금 / 보유종목 / 거래기록
- 수동 Paper 매수·매도
- Paper 계좌 초기화
- SMA 기반 간단 백테스트
- 자동매매 엔진 ON/OFF
- 종목 / 1분봉·일봉 / 1회 주문금액 설정
- Termux 서버 주소 및 관제 토큰 변경

Toss Open API는 OAuth 2.0 인증과 시세·캔들·호가·체결 REST API 및 실시간 체결·호가 WebSocket을 제공합니다. 계좌·자산·주문 계열에는 accountSeq가 필요합니다.