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
