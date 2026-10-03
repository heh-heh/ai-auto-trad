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
